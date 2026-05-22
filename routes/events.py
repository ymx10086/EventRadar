#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event extraction routes.
"""

import csv
import hashlib
import io
import re
import time
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from utils import rss_store
from utils import event_store
from utils import personal_assistant
from utils.auth_manager import auth_manager
from utils.event_automation import event_automation
from utils.fetch_safety import fetch_safety
from utils.rss_poller import rss_poller, FETCH_FULL_CONTENT
from utils.event_extractor import (
    ExtractConfig,
    build_events_ics,
    default_archive_path,
    extract_events_from_archive,
    output_dir_for,
)

router = APIRouter()

EVENT_JOBS = {}
EVENT_JOB_TTL_SECONDS = 3600


def _cleanup_jobs():
    now = int(time.time())
    stale = [
        job_id for job_id, job in EVENT_JOBS.items()
        if now - int(job.get("updated_at", job.get("created_at", now))) > EVENT_JOB_TTL_SECONDS
    ]
    for job_id in stale:
        EVENT_JOBS.pop(job_id, None)


def _job_update(job_id: str, status: str, stage: str, message: str,
                percent: int, detail: Optional[dict] = None):
    now = int(time.time())
    job = EVENT_JOBS.setdefault(job_id, {
        "job_id": job_id,
        "created_at": now,
        "logs": [],
        "result": None,
        "error": "",
    })
    job.update({
        "status": status,
        "stage": stage,
        "message": message,
        "percent": max(0, min(100, int(percent))),
        "updated_at": now,
    })
    if detail:
        job["detail"] = detail
    job.setdefault("logs", []).append({
        "at": now,
        "stage": stage,
        "message": message,
        "percent": job["percent"],
    })
    job["logs"] = job["logs"][-80:]


def _today_str() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def _normalize_date_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return _today_str()
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", text)
    if not match:
        match = re.match(r"^(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})(?:日)?$", text)
    if not match:
        raise HTTPException(status_code=400, detail="日期格式请使用 YYYY-MM-DD，例如 2026-05-21；留空则默认今天")
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def _normalize_range_request(req: "AccountRangeRunRequest") -> "AccountRangeRunRequest":
    start_date = _normalize_date_text(req.start_date)
    end_date = _normalize_date_text(req.end_date or req.start_date)
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    return AccountRangeRunRequest(
        account=req.account,
        start_date=start_date,
        end_date=end_date,
        use_llm=req.use_llm,
        use_vision=req.use_vision,
        download_images=req.download_images,
        max_chars=req.max_chars,
    )


class EventExtractRequest(BaseModel):
    input_path: str = Field("", description="每日文章 JSON 路径；为空时按 date 使用默认归档路径")
    date: Optional[str] = Field(None, description="日期 YYYY-MM-DD")
    use_llm: bool = Field(True, description="是否调用 Minimax 文本模型")
    use_vision: bool = Field(True, description="是否对文章图片调用 Minimax 多模态模型")
    max_chars: int = Field(9000, ge=1000, le=30000, description="每篇文章压缩后的最大字符数")


class AccountEventRunRequest(BaseModel):
    account: str = Field(..., description="公众号名称关键词、alias 或 fakeid")
    date: Optional[str] = Field(None, description="日期 YYYY-MM-DD，默认今天")
    use_llm: bool = Field(True, description="是否调用 Minimax 文本模型")
    use_vision: bool = Field(True, description="是否对文章图片调用 Minimax 多模态模型")
    download_images: bool = Field(True, description="是否下载文章图片")
    max_chars: int = Field(9000, ge=1000, le=30000, description="每篇文章压缩后的最大字符数")


class AccountRangeRunRequest(BaseModel):
    account: str = Field(..., description="公众号名称关键词、alias 或 fakeid")
    start_date: str = ""
    end_date: str = ""
    use_llm: bool = True
    use_vision: bool = True
    download_images: bool = True
    max_chars: int = Field(9000, ge=1000, le=30000)


class EventExtractResponse(BaseModel):
    success: bool
    data: dict = {}


class EventUpdateRequest(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    signup_start_time: Optional[str] = None
    calendar_time: Optional[str] = None
    calendar_time_label: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    organizer: Optional[str] = None
    signup_deadline: Optional[str] = None
    signup_url: Optional[str] = None
    registration_deadline: Optional[str] = None
    registration_link: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    level: Optional[str] = Field(None, pattern="^[SABC]$")
    priority: Optional[str] = Field(None, pattern="^[SABC]$")
    status: Optional[str] = Field(None, pattern="^(pending|confirmed|ignored)$")
    is_favorite: Optional[bool] = None
    favorite: Optional[bool] = None
    reason: Optional[str] = None
    note: Optional[str] = None


class ManualEventRequest(BaseModel):
    mode: str = Field("manual", pattern="^(manual|text|link|image)$")
    pasted_text: str = ""
    link: str = ""
    image_path: str = ""
    title: str = ""
    start_time: str = ""
    end_time: str = ""
    signup_start_time: str = ""
    location: str = ""
    city: str = ""
    organizer: str = ""
    description: str = ""
    registration_deadline: str = ""
    registration_link: str = ""
    tags: List[str] = Field(default_factory=list)
    level: Optional[str] = Field(None, pattern="^[SABC]$")
    status: str = Field("pending", pattern="^(pending|confirmed|ignored)$")


class ProfileRequest(BaseModel):
    identity: str = ""
    profession: str = ""
    research_direction: str = ""
    interests: List[str] = Field(default_factory=list)
    priority_keywords: List[str] = Field(default_factory=list)
    avoid_topics: List[str] = Field(default_factory=list)


class SettingsRequest(BaseModel):
    daily_fetch_enabled: Optional[bool] = None
    daily_fetch_time: Optional[str] = None
    daily_fetch_lookback_days: Optional[int] = Field(None, ge=0, le=30)
    event_retention_days: Optional[int] = Field(None, ge=1, le=365)
    auto_import_calendar: Optional[bool] = None
    use_llm: Optional[bool] = None
    use_vision: Optional[bool] = None
    download_images: Optional[bool] = None
    max_chars: Optional[int] = Field(None, ge=1000, le=30000)
    wechat_fetch_concurrency: Optional[int] = Field(None, ge=1, le=5)
    wechat_fetch_delay_min: Optional[float] = Field(None, ge=0, le=300)
    wechat_fetch_delay_max: Optional[float] = Field(None, ge=0, le=300)
    wechat_account_delay: Optional[float] = Field(None, ge=0, le=600)
    wechat_max_articles_per_account: Optional[int] = Field(None, ge=1, le=100)
    wechat_verification_pause_minutes: Optional[int] = Field(None, ge=0, le=720)
    wechat_verification_stop_threshold: Optional[int] = Field(None, ge=1, le=20)
    wechat_proxy_required: Optional[bool] = None


class SourceRequest(BaseModel):
    source_type: str = Field("link", pattern="^(wechat|link)$")
    fakeid: str = ""
    name: str = ""
    alias: str = ""
    head_img: str = ""
    url: str = ""
    enabled: bool = True
    auto_fetch: bool = True


class SourceUpdateRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    auto_fetch: Optional[bool] = None


@router.get("/profile", response_model=EventExtractResponse, summary="读取个人画像")
async def get_profile():
    return EventExtractResponse(success=True, data={"profile": personal_assistant.get_profile()})


@router.put("/profile", response_model=EventExtractResponse, summary="保存个人画像")
async def save_profile(req: ProfileRequest):
    profile = await run_in_threadpool(personal_assistant.save_profile, req.model_dump())
    return EventExtractResponse(success=True, data={"profile": profile})


@router.get("/settings", response_model=EventExtractResponse, summary="读取个人活动助手设置")
async def get_settings():
    settings = personal_assistant.get_settings()
    status = event_automation.status()
    return EventExtractResponse(success=True, data={"settings": settings, "automation": status, "fetch_safety": fetch_safety.status()})


@router.put("/settings", response_model=EventExtractResponse, summary="保存个人活动助手设置")
async def save_settings(req: SettingsRequest):
    updates = req.model_dump(exclude_unset=True)
    settings = await run_in_threadpool(personal_assistant.save_settings, updates)
    event_automation.configure(settings)
    return EventExtractResponse(success=True, data={"settings": settings, "automation": event_automation.status(), "fetch_safety": fetch_safety.status()})


@router.get("/sources", response_model=EventExtractResponse, summary="读取关注的信息源")
async def list_sources():
    sources = await run_in_threadpool(personal_assistant.list_sources)
    return EventExtractResponse(success=True, data={"source_count": len(sources), "sources": sources})


@router.post("/sources", response_model=EventExtractResponse, summary="添加关注的信息源")
async def add_source(req: SourceRequest):
    payload = req.model_dump()
    if payload.get("source_type") == "wechat" and not payload.get("fakeid"):
        query = (payload.get("name") or payload.get("alias") or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="请输入公众号名称")
        target = await _resolve_account(query)
        if not target:
            raise HTTPException(status_code=404, detail=f"未找到公众号: {query}")
        payload.update({
            "fakeid": target["fakeid"],
            "name": target.get("nickname") or query,
            "alias": target.get("alias", ""),
            "head_img": target.get("head_img", ""),
        })
    try:
        source = await run_in_threadpool(personal_assistant.add_source, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventExtractResponse(success=True, data={"source": source})


@router.patch("/sources/{source_id:path}", response_model=EventExtractResponse, summary="更新信息源")
async def update_source(source_id: str, req: SourceUpdateRequest):
    source = await run_in_threadpool(
        personal_assistant.update_source,
        source_id,
        req.model_dump(exclude_unset=True),
    )
    if not source:
        raise HTTPException(status_code=404, detail="信息源不存在")
    return EventExtractResponse(success=True, data={"source": source})


@router.delete("/sources/{source_id:path}", response_model=EventExtractResponse, summary="删除信息源")
async def delete_source(source_id: str):
    removed = await run_in_threadpool(personal_assistant.delete_source, source_id)
    if not removed:
        raise HTTPException(status_code=404, detail="信息源不存在")
    return EventExtractResponse(success=True, data={"removed": True})


@router.post("/manual", response_model=EventExtractResponse, summary="手动添加活动")
async def add_manual_event(req: ManualEventRequest):
    payload = req.model_dump()
    text = " ".join([
        payload.get("title", ""),
        payload.get("pasted_text", ""),
        payload.get("description", ""),
        payload.get("link", ""),
    ]).strip()
    date_match = re.search(r"\d{4}[-/年]\s*\d{1,2}[-/月]\s*\d{1,2}(?:日)?", text)
    time_match = re.search(r"\d{1,2}:\d{2}(?:\s*[-~至]\s*\d{1,2}:\d{2})?", text)
    url_match = re.search(r"https?://[^\s<>\"]+", text)
    location_match = re.search(r"(?:地点|地址|Location|Venue)\s*[:：]?\s*([^\n。；;]{2,80})", text, re.IGNORECASE)
    deadline_match = re.search(r"(?:报名截止|截止时间|Deadline)\s*[:：]?\s*([^\n。；;]{2,80})", text, re.IGNORECASE)
    title = payload.get("title") or (text[:40] if text else "未命名活动")
    source_url = payload.get("link") or payload.get("registration_link") or ""
    inferred_start = " ".join(item for item in [
        date_match.group(0) if date_match else "",
        time_match.group(0) if time_match else "",
    ] if item).strip()
    event_id_seed = "|".join([
        title,
        payload.get("start_time", ""),
        payload.get("location", ""),
        source_url,
        str(time.time()),
    ])
    event = {
        "id": hashlib.sha1(event_id_seed.encode("utf-8")).hexdigest()[:16],
        "title": title,
        "start_time": payload.get("start_time") or inferred_start,
        "end_time": payload.get("end_time", ""),
        "signup_start_time": payload.get("signup_start_time", ""),
        "location": payload.get("location") or (location_match.group(1).strip() if location_match else ""),
        "city": payload.get("city", ""),
        "organizer": payload.get("organizer", ""),
        "description": payload.get("description") or payload.get("pasted_text", ""),
        "registration_deadline": payload.get("registration_deadline") or (deadline_match.group(1).strip() if deadline_match else ""),
        "registration_link": payload.get("registration_link") or source_url or (url_match.group(0) if url_match else ""),
        "source_type": payload.get("mode") or "manual",
        "source_name": "手动添加",
        "source_url": source_url,
        "tags": payload.get("tags", []),
        "level": payload.get("level") or "",
        "status": payload.get("status") or "pending",
        "is_favorite": False,
        "created_at": int(time.time()),
    }
    event = personal_assistant.normalize_event(event)
    saved_count = await run_in_threadpool(event_store.save_events, [event])
    await run_in_threadpool(event_store.cleanup_duplicate_events)
    saved = await run_in_threadpool(event_store.get_event, event["id"])
    return EventExtractResponse(success=True, data={"saved_count": saved_count, "event": saved})


@router.post("/extract", response_model=EventExtractResponse, summary="从每日文章 JSON 抽取活动")
async def extract_events(req: EventExtractRequest):
    """
    从 `data/daily_archives/YYYY-MM-DD/articles.json` 或指定 JSON 文件中抽取活动信息，
    输出 `events.json`、`events.csv` 和 `calendar.ics`。
    """
    input_path = req.input_path.strip() or str(default_archive_path(req.date))
    try:
        payload = await run_in_threadpool(
            extract_events_from_archive,
            input_path,
            ExtractConfig(
                use_llm=req.use_llm,
                use_vision=req.use_vision,
                max_chars=req.max_chars,
            ),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"活动抽取失败: {str(e)}")

    normalized_events = await run_in_threadpool(personal_assistant.normalize_events, payload.get("events", []))
    saved_count = await run_in_threadpool(event_store.save_events, normalized_events)
    cleanup_result = await run_in_threadpool(event_store.cleanup_duplicate_events)

    return EventExtractResponse(
        success=True,
        data={
            "date": payload.get("date"),
            "article_count": payload.get("article_count"),
            "selected_article_count": payload.get("selected_article_count"),
            "event_count": payload.get("event_count"),
            "llm_enabled": payload.get("llm_enabled"),
            "llm_available": payload.get("llm_available"),
            "vision_enabled": payload.get("vision_enabled"),
            "outputs": payload.get("outputs", {}),
            "saved_count": saved_count,
            "dedupe": cleanup_result,
            "events": normalized_events,
        },
    )


@router.post("/run-account", response_model=EventExtractResponse,
             summary="输入公众号后完成订阅、抓取、归档、活动抽取")
async def run_account_event_pipeline(req: AccountEventRunRequest):
    """
    输入公众号名称、alias 或 fakeid，一次性完成：
    搜索公众号 -> 添加订阅 -> 拉取最新文章 -> 生成每日文章 JSON -> 活动抽取 -> 导出日历。
    """
    account = req.account.strip()
    if not account:
        raise HTTPException(status_code=400, detail="account 不能为空")

    target = await _resolve_account(account)
    if not target:
        raise HTTPException(status_code=404, detail=f"未找到公众号: {account}")

    rss_store.add_subscription(
        fakeid=target["fakeid"],
        nickname=target.get("nickname", ""),
        alias=target.get("alias", ""),
        head_img=target.get("head_img", ""),
    )

    await _poll_one_account(target["fakeid"])

    from utils.daily_archive import archive_daily_articles, get_archive_file

    archive_payload = await run_in_threadpool(
        archive_daily_articles,
        req.date,
        target["fakeid"],
        req.download_images,
        False,
    )
    archive_file = get_archive_file(archive_payload["date"])
    extract_payload = await run_in_threadpool(
        extract_events_from_archive,
        str(archive_file),
        ExtractConfig(
            use_llm=req.use_llm,
            use_vision=req.use_vision,
            max_chars=req.max_chars,
        ),
    )
    normalized_events = await run_in_threadpool(personal_assistant.normalize_events, extract_payload.get("events", []))
    saved_count = await run_in_threadpool(event_store.save_events, normalized_events)
    cleanup_result = await run_in_threadpool(event_store.cleanup_duplicate_events)

    return EventExtractResponse(
        success=True,
        data={
            "account": target,
            "date": extract_payload.get("date"),
            "archive": {
                "archive_file": str(archive_file),
                "archive_dir": archive_payload.get("archive_dir"),
                "image_dir": archive_payload.get("image_dir"),
                "article_count": archive_payload.get("article_count"),
                "image_count": archive_payload.get("image_count"),
                "downloaded_image_count": archive_payload.get("downloaded_image_count"),
                "failed_image_count": archive_payload.get("failed_image_count"),
            },
            "article_count": extract_payload.get("article_count"),
            "selected_article_count": extract_payload.get("selected_article_count"),
            "event_count": extract_payload.get("event_count"),
            "llm_enabled": extract_payload.get("llm_enabled"),
            "llm_available": extract_payload.get("llm_available"),
            "vision_enabled": extract_payload.get("vision_enabled"),
            "outputs": extract_payload.get("outputs", {}),
            "saved_count": saved_count,
            "dedupe": cleanup_result,
            "events": normalized_events,
        },
    )


@router.post("/run-account-range", response_model=EventExtractResponse,
             summary="按公众号和日期范围批量提取活动")
async def run_account_event_range(req: AccountRangeRunRequest):
    req = _normalize_range_request(req)
    return EventExtractResponse(success=True, data=await _run_account_range_pipeline(req))


@router.post("/run-account-range/progress", response_model=EventExtractResponse,
             summary="启动带进度的公众号日期范围提取任务")
async def start_account_event_range_job(req: AccountRangeRunRequest):
    req = _normalize_range_request(req)
    if not req.account.strip():
        raise HTTPException(status_code=400, detail="account 不能为空")

    _cleanup_jobs()
    job_id = uuid.uuid4().hex[:16]
    _job_update(job_id, "queued", "queued", "任务已创建，等待开始抓取", 1)
    asyncio.create_task(_run_account_range_job(job_id, req))
    return EventExtractResponse(success=True, data={"job_id": job_id, "job": EVENT_JOBS[job_id]})


@router.get("/jobs/{job_id}", response_model=EventExtractResponse, summary="读取活动提取任务进度")
async def get_event_job(job_id: str):
    _cleanup_jobs()
    job = EVENT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return EventExtractResponse(success=True, data={"job": job})


async def _run_account_range_job(job_id: str, req: AccountRangeRunRequest):
    try:
        result = await _run_account_range_pipeline(
            req,
            lambda stage, message, percent, detail=None: _job_update(
                job_id,
                "running",
                stage,
                message,
                percent,
                detail,
            ),
        )
        EVENT_JOBS[job_id]["result"] = result
        _job_update(
            job_id,
            "success",
            "done",
            "完成：写入日历 %d 个活动" % int(result.get("saved_count") or 0),
            100,
            {
                "article_count": result.get("article_count", 0),
                "event_count": result.get("event_count", 0),
                "saved_count": result.get("saved_count", 0),
            },
        )
    except Exception as exc:
        EVENT_JOBS.setdefault(job_id, {})["error"] = str(exc)
        _job_update(job_id, "failed", "failed", str(exc), 100)


async def _run_account_range_pipeline(req: AccountRangeRunRequest, progress=None):
    req = _normalize_range_request(req)

    def emit(stage: str, message: str, percent: int, detail: Optional[dict] = None):
        if progress:
            progress(stage, message, percent, detail)

    account = req.account.strip()
    if not account:
        raise HTTPException(status_code=400, detail="account 不能为空")
    emit("resolve", "正在搜索公众号：" + account, 5)
    target = await _resolve_account(account)
    if not target:
        raise HTTPException(status_code=404, detail=f"未找到公众号: {account}")

    emit("subscribe", "已找到公众号：%s，正在加入关注源" % (target.get("nickname") or target["fakeid"]), 12)
    rss_store.add_subscription(
        fakeid=target["fakeid"],
        nickname=target.get("nickname", ""),
        alias=target.get("alias", ""),
        head_img=target.get("head_img", ""),
    )
    emit("poll", "正在访问公众号文章列表并抓取正文内容", 18, {"fakeid": target["fakeid"]})
    await _poll_one_account(target["fakeid"])

    from datetime import date as Date, timedelta
    from utils.daily_archive import archive_daily_articles, get_archive_file

    start = Date.fromisoformat(req.start_date)
    end = Date.fromisoformat(req.end_date)
    total_days = (end - start).days + 1
    cursor = start
    all_events = []
    archives = []
    total_articles = 0
    total_selected = 0
    day_index = 0
    while cursor <= end:
        day_index += 1
        date_text = cursor.isoformat()
        base_percent = 22 + int((day_index - 1) / max(1, total_days) * 58)
        emit("archive", "正在整理 %s 的文章归档并下载图片" % date_text, base_percent, {"date": date_text, "day": day_index, "total_days": total_days})
        archive_payload = await run_in_threadpool(
            archive_daily_articles,
            date_text,
            target["fakeid"],
            req.download_images,
            False,
        )
        archive_file = get_archive_file(archive_payload["date"])
        emit(
            "extract",
            "正在分析 %s：规则初筛、压缩长文、调用模型抽取活动" % date_text,
            min(88, base_percent + 18),
            {
                "date": date_text,
                "article_count": archive_payload.get("article_count", 0),
                "image_count": archive_payload.get("image_count", 0),
            },
        )
        extract_payload = await run_in_threadpool(
            extract_events_from_archive,
            str(archive_file),
            ExtractConfig(
                use_llm=req.use_llm,
                use_vision=req.use_vision,
                max_chars=req.max_chars,
            ),
        )
        events = await run_in_threadpool(personal_assistant.normalize_events, extract_payload.get("events", []))
        all_events.extend(events)
        total_articles += int(extract_payload.get("article_count") or 0)
        total_selected += int(extract_payload.get("selected_article_count") or 0)
        emit(
            "dedupe",
            "%s 分析完成：候选文章 %d 篇，活动 %d 个，正在合并去重" % (
                date_text,
                int(extract_payload.get("selected_article_count") or 0),
                len(events),
            ),
            min(92, base_percent + 28),
            {"date": date_text, "event_count": len(events)},
        )
        archives.append({
            "date": date_text,
            "archive_file": str(archive_file),
            "article_count": archive_payload.get("article_count", 0),
            "event_count": len(events),
        })
        cursor += timedelta(days=1)

    emit("save", "正在根据个人画像分级，并写入我的活动日历", 94, {"event_count": len(all_events)})
    saved_count = await run_in_threadpool(event_store.save_events, all_events)
    cleanup_result = await run_in_threadpool(event_store.cleanup_duplicate_events)
    return {
        "account": target,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "archives": archives,
        "article_count": total_articles,
        "selected_article_count": total_selected,
        "event_count": len(all_events),
        "saved_count": saved_count,
        "dedupe": cleanup_result,
        "events": all_events,
    }


async def _resolve_account(account: str) -> Optional[dict]:
    if account.endswith("==") or account.startswith("Mz") or account.startswith("Mj"):
        sub = rss_store.get_subscription(account)
        return {
            "fakeid": account,
            "nickname": sub.get("nickname", "") if sub else account,
            "alias": sub.get("alias", "") if sub else "",
            "head_img": sub.get("head_img", "") if sub else "",
            "matched_by": "fakeid",
        }

    local_subs = rss_store.list_subscriptions()
    exact = next(
        (
            sub for sub in local_subs
            if account == (sub.get("nickname") or "") or account == (sub.get("alias") or "")
        ),
        None,
    )
    fuzzy = next(
        (
            sub for sub in local_subs
            if account and (
                account in (sub.get("nickname") or "") or
                account.lower() in (sub.get("alias") or "").lower()
            )
        ),
        None,
    )
    sub = exact or fuzzy
    if sub:
        return {
            "fakeid": sub["fakeid"],
            "nickname": sub.get("nickname", ""),
            "alias": sub.get("alias", ""),
            "head_img": sub.get("head_img", ""),
            "matched_by": "local_subscription",
        }

    creds = auth_manager.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="服务器未登录，请先扫码登录")

    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(
            "https://mp.weixin.qq.com/cgi-bin/searchbiz",
            params={
                "action": "search_biz",
                "token": creds["token"],
                "lang": "zh_CN",
                "f": "json",
                "ajax": 1,
                "query": account,
                "begin": 0,
                "count": 5,
            },
            headers={
                "Cookie": creds["cookie"],
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
    data = resp.json()
    if data.get("base_resp", {}).get("ret") != 0:
        raise HTTPException(status_code=502, detail=f"公众号搜索失败: {data.get('base_resp', {}).get('err_msg', 'unknown')}")

    accounts = data.get("list", [])
    if not accounts:
        return None

    def score(item):
        nickname = item.get("nickname", "")
        alias = item.get("alias", "")
        if nickname == account or alias == account:
            return 100
        if account in nickname:
            return 80
        if account.lower() in alias.lower():
            return 70
        return 10

    best = sorted(accounts, key=score, reverse=True)[0]
    return {
        "fakeid": best.get("fakeid", ""),
        "nickname": best.get("nickname", ""),
        "alias": best.get("alias", ""),
        "head_img": best.get("round_head_img", ""),
        "matched_by": "search",
    }


async def _poll_one_account(fakeid: str):
    if not rss_poller.is_running:
        raise HTTPException(status_code=503, detail="轮询器未启动")

    creds = auth_manager.get_credentials()
    if not creds or not creds.get("token") or not creds.get("cookie"):
        raise HTTPException(status_code=401, detail="服务器未登录，请先扫码登录")

    articles = await rss_poller._fetch_article_list(fakeid, creds)
    if articles and FETCH_FULL_CONTENT:
        articles = await rss_poller._enrich_articles_content(fakeid, articles)
    if articles:
        rss_store.save_articles(fakeid, articles, source="poll")
    rss_store.update_last_poll(fakeid)


@router.get("/latest", response_model=EventExtractResponse, summary="读取指定日期活动抽取结果")
async def get_latest_events(date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    if date:
        out_dir = output_dir_for(date)
    else:
        events_root = output_dir_for("1970-01-01").parent
        candidates = sorted(
            (p for p in events_root.iterdir() if (p / "events.json").exists()),
            key=lambda p: p.name,
            reverse=True,
        ) if events_root.exists() else []
        out_dir = candidates[0] if candidates else output_dir_for(None)

    path = out_dir / "events.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="活动结果不存在，请先运行抽取")
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["events"] = personal_assistant.normalize_events(payload.get("events", []))
    return EventExtractResponse(success=True, data=payload)


@router.get("/list", response_model=EventExtractResponse, summary="获取活动库事件列表")
async def list_stored_events(
    start: Optional[str] = Query(None, description="开始时间 ISO 字符串"),
    end: Optional[str] = Query(None, description="结束时间 ISO 字符串"),
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|ignored)$"),
    priority: Optional[str] = Query(None, pattern="^[SABC]$"),
    account: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="标题、地点、正文、来源关键词"),
    favorite: Optional[bool] = Query(None, description="仅返回收藏或未收藏活动"),
    include_ignored: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
):
    events = await run_in_threadpool(
        event_store.list_events,
        start,
        end,
        status,
        priority,
        account,
        include_ignored,
        limit,
        category,
        q,
        tag,
        favorite,
    )
    summary = await run_in_threadpool(event_store.summarize_events, events)
    return EventExtractResponse(
        success=True,
        data={
            "event_count": len(events),
            **summary,
            "events": events,
        },
    )


@router.get("/export.csv", summary="导出活动库 CSV")
async def export_stored_events_csv(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|ignored)$"),
    priority: Optional[str] = Query(None, pattern="^[SABC]$"),
    account: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    favorite: Optional[bool] = Query(None),
    include_ignored: bool = Query(False),
    limit: int = Query(2000, ge=1, le=5000),
):
    events = await run_in_threadpool(
        event_store.list_events,
        start,
        end,
        status,
        priority,
        account,
        include_ignored,
        limit,
        category,
        q,
        tag,
        favorite,
    )
    fields = [
        "id", "title", "start_time", "end_time", "location", "city",
        "organizer", "description", "registration_deadline",
        "registration_link", "source_type", "source_name", "source_url",
        "tags", "level", "reason", "status", "created_at",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for event in events:
        row = {field: event.get(field, "") for field in fields}
        row["tags"] = "，".join(event.get("tags", []))
        writer.writerow(row)
    content = "\ufeff" + buffer.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="eventradar_events.csv"'},
    )


@router.get("/upcoming", response_model=EventExtractResponse, summary="获取近期活动")
async def upcoming_stored_events(
    days: int = Query(14, ge=0, le=365),
    status: str = Query("confirmed", pattern="^(pending|confirmed|ignored)$"),
    limit: int = Query(50, ge=1, le=500),
):
    events = await run_in_threadpool(event_store.upcoming_events, days, status, limit)
    summary = await run_in_threadpool(event_store.summarize_events, events)
    return EventExtractResponse(
        success=True,
        data={
            "days": days,
            "event_count": len(events),
            **summary,
            "events": events,
        },
    )


@router.post("/cleanup", response_model=EventExtractResponse, summary="删除超过保留期的未收藏活动")
async def cleanup_old_events(retention_days: int = Query(15, ge=1, le=365)):
    result = await run_in_threadpool(event_store.delete_old_unfavorited_events, retention_days)
    return EventExtractResponse(success=True, data=result)


@router.post("/cleanup-duplicates", response_model=EventExtractResponse, summary="清理低质量重复活动")
async def cleanup_duplicate_events():
    result = await run_in_threadpool(event_store.cleanup_duplicate_events)
    return EventExtractResponse(success=True, data=result)


@router.get("/calendar.ics", summary="活动库 ICS 订阅")
async def stored_events_ics(
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|ignored)$"),
    priority: Optional[str] = Query(None, pattern="^[SABC]$"),
    account: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    include_ignored: bool = Query(False),
):
    events = await run_in_threadpool(
        event_store.list_events,
        None,
        None,
        status,
        priority,
        account,
        include_ignored,
        2000,
        category,
        None,
    )
    content = build_events_ics(events)
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="eventradar_events.ics"'},
    )


@router.patch("/{event_id}", response_model=EventExtractResponse, summary="更新活动状态、分级或字段")
async def update_stored_event(event_id: str, req: EventUpdateRequest):
    updates = req.model_dump(exclude_unset=True)
    event = await run_in_threadpool(event_store.update_event, event_id, updates)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return EventExtractResponse(success=True, data={"event": event})


@router.post("/{event_id}/favorite", response_model=EventExtractResponse, summary="收藏或取消收藏活动")
async def favorite_stored_event(event_id: str, favorite: bool = True):
    event = await run_in_threadpool(event_store.update_event, event_id, {"is_favorite": favorite})
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return EventExtractResponse(success=True, data={"event": event})


@router.delete("/{event_id}", response_model=EventExtractResponse, summary="彻底删除活动")
async def delete_stored_event(event_id: str, delete_files: bool = True):
    result = await run_in_threadpool(event_store.delete_event, event_id, delete_files)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="事件不存在")
    return EventExtractResponse(success=True, data=result)


@router.get("/download/{date}/{filename}", summary="下载活动导出文件")
async def download_event_file(
    date: str,
    filename: str,
):
    if filename not in {"events.json", "events.csv", "calendar.ics"}:
        raise HTTPException(status_code=400, detail="filename must be events.json, events.csv, or calendar.ics")
    path = output_dir_for(date) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在，请先运行抽取")

    media_type = {
        "events.json": "application/json; charset=utf-8",
        "events.csv": "text/csv; charset=utf-8",
        "calendar.ics": "text/calendar; charset=utf-8",
    }[filename]
    return FileResponse(Path(path), media_type=media_type, filename=filename)
