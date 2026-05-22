#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automation routes for event extraction and account discovery.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils import rss_store
from utils.account_discovery import (
    discover_accounts,
    load_recommendations,
    parse_keywords,
    subscribe_top_candidates,
)
from utils.automation_history import list_runs
from utils.event_automation import event_automation

router = APIRouter()


class AutomationResponse(BaseModel):
    success: bool
    data: dict = {}


class EventPipelineRunRequest(BaseModel):
    date: Optional[str] = Field(None, description="日期 YYYY-MM-DD，默认今天")
    lookback_days: Optional[int] = Field(None, ge=0, le=30, description="包含今天往前 N 天；0 表示只跑当天")
    poll: bool = Field(True, description="运行前是否先轮询订阅公众号")
    use_llm: Optional[bool] = Field(None, description="是否调用 Minimax 文本抽取，空值使用环境变量")
    use_vision: Optional[bool] = Field(None, description="是否调用 Minimax 海报识别，空值使用环境变量")
    download_images: Optional[bool] = Field(None, description="是否下载图片，空值使用环境变量")
    max_chars: int = Field(9000, ge=1000, le=30000)
    run_discovery: Optional[bool] = Field(None, description="是否顺带发现候选公众号")
    discovery_subscribe_top: Optional[int] = Field(None, ge=0, le=20, description="发现后自动订阅前 N 个未订阅候选")


class AccountDiscoveryRequest(BaseModel):
    keywords: List[str] = Field(default_factory=list, description="搜索关键词；为空则使用默认/环境变量关键词")
    limit_per_keyword: int = Field(5, ge=1, le=10)
    max_results: int = Field(30, ge=1, le=100)
    min_score: int = Field(35, ge=0, le=100)
    subscribe_top: int = Field(0, ge=0, le=20, description="自动订阅前 N 个未订阅候选；默认只推荐不订阅")


class SubscribeCandidatesRequest(BaseModel):
    fakeids: List[str] = Field(default_factory=list)


@router.get("/status", response_model=AutomationResponse, summary="自动化状态")
async def automation_status():
    return AutomationResponse(success=True, data=event_automation.status())


@router.get("/runs", response_model=AutomationResponse, summary="自动化运行历史")
async def automation_runs(limit: int = 30):
    limit = max(1, min(limit, 200))
    runs = list_runs(limit)
    return AutomationResponse(
        success=True,
        data={
            "run_count": len(runs),
            "runs": runs,
        },
    )


@router.post("/run-events", response_model=AutomationResponse, summary="立即运行活动自动化")
async def run_event_pipeline(req: EventPipelineRunRequest):
    try:
        result = await event_automation.run_once(
            date=req.date,
            poll=req.poll,
            use_llm=req.use_llm,
            use_vision=req.use_vision,
            download_images=req.download_images,
            max_chars=req.max_chars,
            run_discovery=req.run_discovery,
            discovery_subscribe_top=req.discovery_subscribe_top,
            lookback_days=req.lookback_days,
            source="manual",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409 if "正在运行" in str(exc) else 400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"自动化运行失败: {str(exc)}")
    return AutomationResponse(success=True, data=result)


@router.get("/discover-accounts", response_model=AutomationResponse, summary="读取最近一次公众号发现结果")
async def latest_account_discovery():
    return AutomationResponse(success=True, data=load_recommendations())


@router.post("/discover-accounts", response_model=AutomationResponse, summary="搜索并推荐公众号")
async def run_account_discovery(req: AccountDiscoveryRequest):
    keywords = [item.strip() for item in req.keywords if item.strip()] or parse_keywords()
    try:
        payload = await discover_accounts(
            keywords=keywords,
            limit_per_keyword=req.limit_per_keyword,
            max_results=req.max_results,
            min_score=req.min_score,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=401 if "未登录" in str(exc) else 400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"公众号发现失败: {str(exc)}")

    subscribed = subscribe_top_candidates(payload, req.subscribe_top)
    payload["subscribed_count"] = len(subscribed)
    payload["subscribed"] = subscribed
    return AutomationResponse(success=True, data=payload)


@router.post("/subscribe-candidates", response_model=AutomationResponse, summary="订阅推荐公众号")
async def subscribe_candidates(req: SubscribeCandidatesRequest):
    latest = load_recommendations()
    by_fakeid = {item["fakeid"]: item for item in latest.get("candidates", [])}
    subscribed = []
    missing = []
    for fakeid in req.fakeids:
        item = by_fakeid.get(fakeid)
        if not item:
            missing.append(fakeid)
            continue
        added = rss_store.add_subscription(
            fakeid=item["fakeid"],
            nickname=item.get("nickname", ""),
            alias=item.get("alias", ""),
            head_img=item.get("head_img", ""),
        )
        if added:
            subscribed.append(item)
    return AutomationResponse(
        success=True,
        data={
            "requested_count": len(req.fakeids),
            "subscribed_count": len(subscribed),
            "missing": missing,
            "subscribed": subscribed,
        },
    )
