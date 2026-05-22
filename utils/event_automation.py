#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automation for the daily event pipeline.

Runs the existing RSS polling, daily archive, event extraction, event store, and
optional account discovery steps behind a small scheduler.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from utils.automation_history import append_run
from utils import event_store, rss_store
from utils.account_discovery import discover_accounts, parse_keywords, subscribe_top_candidates
from utils.daily_archive import archive_daily_articles, get_archive_file
from utils.event_extractor import ExtractConfig, extract_events_from_archive
from utils.fetch_safety import FetchSafetyPausedError, fetch_safety
from utils.personal_assistant import get_settings, normalize_events
from utils.rss_poller import rss_poller
from utils.webhook import webhook


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def should_notify_automation(source: str) -> bool:
    if not _env_bool("EVENT_AUTOMATION_WEBHOOK_ENABLED", True):
        return False
    if source == "manual" and not _env_bool("EVENT_AUTOMATION_NOTIFY_MANUAL", False):
        return False
    return True


def _format_upcoming_events(events, max_items: int = 8) -> str:
    if not events:
        return "未来周期内暂无已确认活动"
    lines = []
    for index, event in enumerate(events[:max_items], 1):
        title = event.get("title") or "未命名活动"
        start_time = event.get("start_time") or "时间待定"
        location = event.get("location") or "地点待定"
        account = event.get("account") or "未知来源"
        lines.append(f"{index}. {start_time}｜{title}｜{location}｜{account}")
    if len(events) > max_items:
        lines.append(f"... 还有 {len(events) - max_items} 个活动")
    return "\n".join(lines)


class EventAutomation:
    def __init__(self):
        self.enabled = _env_bool("EVENT_AUTOMATION_ENABLED", False)
        self.schedule_time = os.getenv("EVENT_AUTOMATION_TIME", "07:30")
        self.timezone = os.getenv("DAILY_ARCHIVE_TIMEZONE", "Asia/Shanghai")
        self.discovery_enabled = _env_bool("ACCOUNT_DISCOVERY_ENABLED", False)
        self.discovery_auto_subscribe_top = int(os.getenv("ACCOUNT_DISCOVERY_AUTO_SUBSCRIBE_TOP", "0"))
        self.lookback_days = int(os.getenv("EVENT_AUTOMATION_LOOKBACK_DAYS", "0"))
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        self._last_run_date = ""
        self._last_run_at = 0
        self._last_result: Dict = {}
        self._last_error = ""
        self._progress: Dict = {
            "active": False,
            "status": "idle",
            "stage": "idle",
            "message": "空闲",
            "percent": 0,
            "logs": [],
            "updated_at": 0,
            "source": "",
        }

    def _set_progress(self, status: str, stage: str, message: str, percent: int,
                      detail: Optional[Dict] = None):
        now = int(time.time())
        active = status in {"queued", "running"}
        self._progress.update({
            "active": active,
            "status": status,
            "stage": stage,
            "message": message,
            "percent": max(0, min(100, int(percent))),
            "updated_at": now,
        })
        if detail:
            self._progress["detail"] = detail
        self._progress.setdefault("logs", []).append({
            "at": now,
            "stage": stage,
            "message": message,
            "percent": self._progress["percent"],
        })
        self._progress["logs"] = self._progress["logs"][-80:]

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> Dict:
        try:
            subscription_count = len(rss_store.list_subscriptions())
        except Exception:
            subscription_count = 0
        return {
            "running": self._running,
            "enabled": self.enabled,
            "schedule_time": self.schedule_time,
            "timezone": self.timezone,
            "discovery_enabled": self.discovery_enabled,
            "discovery_auto_subscribe_top": self.discovery_auto_subscribe_top,
            "lookback_days": self.lookback_days,
            "last_run_date": self._last_run_date,
            "last_run_at": self._last_run_at,
            "last_error": self._last_error,
            "last_result": self._last_result,
            "progress": self._progress,
            "subscription_count": subscription_count,
            "fetch_safety": fetch_safety.status(),
        }

    def configure(self, settings: Dict):
        self.enabled = bool(settings.get("daily_fetch_enabled", self.enabled))
        self.schedule_time = str(settings.get("daily_fetch_time") or self.schedule_time)
        self.lookback_days = max(0, min(30, int(settings.get("daily_fetch_lookback_days", self.lookback_days) or 0)))
        self.discovery_enabled = bool(settings.get("discovery_enabled", self.discovery_enabled))
        if "discovery_auto_subscribe_top" in settings:
            self.discovery_auto_subscribe_top = int(settings.get("discovery_auto_subscribe_top") or 0)

    async def _loop(self):
        while self._running:
            try:
                if self.enabled and self._is_due():
                    await self.run_once(source="scheduled")
            except Exception as exc:
                self._last_error = str(exc)
            await asyncio.sleep(60)

    def _is_due(self) -> bool:
        now = datetime.now(ZoneInfo(self.timezone))
        today = now.strftime("%Y-%m-%d")
        if self._last_run_date == today:
            return False
        try:
            hour_text, minute_text = self.schedule_time.split(":", 1)
            scheduled = now.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
        except Exception:
            scheduled = now.replace(hour=7, minute=30, second=0, microsecond=0)
        return now >= scheduled

    async def run_once(
        self,
        date: Optional[str] = None,
        poll: bool = True,
        use_llm: Optional[bool] = None,
        use_vision: Optional[bool] = None,
        download_images: Optional[bool] = None,
        max_chars: int = 9000,
        run_discovery: Optional[bool] = None,
        discovery_subscribe_top: Optional[int] = None,
        source: str = "manual",
        lookback_days: Optional[int] = None,
    ) -> Dict:
        if self._lock.locked():
            raise RuntimeError("活动自动化任务正在运行")

        async with self._lock:
            started_at = int(time.time())
            self._set_progress("running", "start", "正在准备自动化抓取", 1, {"source": source})
            self._progress["source"] = source
            settings = get_settings()
            if use_llm is None:
                use_llm = bool(settings.get("use_llm", _env_bool("EVENT_AUTOMATION_USE_LLM", True)))
            if use_vision is None:
                use_vision = bool(settings.get("use_vision", _env_bool("EVENT_AUTOMATION_USE_VISION", False)))
            if download_images is None:
                download_images = bool(settings.get("download_images", _env_bool("DAILY_ARCHIVE_DOWNLOAD_IMAGES", True)))
            if lookback_days is None:
                lookback_days = int(settings.get("daily_fetch_lookback_days", self.lookback_days) or 0)
            lookback_days = max(0, min(30, int(lookback_days or 0)))
            if run_discovery is None:
                run_discovery = self.discovery_enabled
            if discovery_subscribe_top is None:
                discovery_subscribe_top = self.discovery_auto_subscribe_top

            params = {
                "date": date,
                "poll": poll,
                "use_llm": use_llm,
                "use_vision": use_vision,
                "download_images": download_images,
                "max_chars": max_chars,
                "run_discovery": run_discovery,
                "discovery_subscribe_top": discovery_subscribe_top,
                "source": source,
                "lookback_days": lookback_days,
            }

            try:
                if fetch_safety.is_paused():
                    message = fetch_safety.pause_message()
                    self._set_progress("failed", "safety_pause", message, 100, fetch_safety.status())
                    raise FetchSafetyPausedError(message)
                self._set_progress("running", "sources", "正在读取参与定时抓取的公众号", 5)
                selected_subs = rss_store.list_auto_fetch_subscriptions()
                selected_fakeids = [sub["fakeid"] for sub in selected_subs]
                if poll:
                    if not rss_poller.is_running:
                        raise RuntimeError("RSS 轮询器未启动")
                    if fetch_safety.is_paused():
                        message = fetch_safety.pause_message()
                        self._set_progress("failed", "safety_pause", message, 100, fetch_safety.status())
                        raise FetchSafetyPausedError(message)
                    self._set_progress(
                        "running",
                        "poll",
                        "正在轮询 %d 个公众号最新文章" % len(selected_fakeids),
                        10,
                    )
                    await rss_poller.poll_now(fakeids=selected_fakeids)

                tz = ZoneInfo(self.timezone)
                end_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now(tz).date()
                start_date = end_date - timedelta(days=lookback_days)
                day_payloads = []
                all_events = []
                total_articles = 0
                total_accounts = 0
                total_downloaded = 0
                total_failed = 0
                total_selected = 0
                total_extracted = 0
                cursor = start_date
                total_days = (end_date - start_date).days + 1
                total_steps = max(1, total_days * max(1, len(selected_fakeids)))
                current_step = 0
                while cursor <= end_date:
                    date_text = cursor.isoformat()
                    day_events = []
                    day_articles = 0
                    day_accounts = 0
                    day_downloaded = 0
                    day_failed = 0
                    day_selected = 0
                    day_extracted = 0
                    day_outputs = {}

                    for fakeid in selected_fakeids:
                        current_step += 1
                        account = next((sub for sub in selected_subs if sub.get("fakeid") == fakeid), {})
                        base_percent = 15 + int((current_step - 1) / total_steps * 65)
                        self._set_progress(
                            "running",
                            "archive",
                            "正在整理 %s｜%s 的文章和图片" % (date_text, account.get("nickname") or fakeid[:8]),
                            base_percent,
                            {"date": date_text, "fakeid": fakeid},
                        )
                        archive_payload = await asyncio.to_thread(
                            archive_daily_articles,
                            date_text,
                            fakeid,
                            download_images,
                            False,
                        )
                        archive_file = get_archive_file(archive_payload["date"])
                        self._set_progress(
                            "running",
                            "extract",
                            "正在抽取 %s｜%s 的活动信息" % (date_text, account.get("nickname") or fakeid[:8]),
                            min(88, base_percent + 6),
                            {
                                "date": date_text,
                                "fakeid": fakeid,
                                "article_count": archive_payload.get("article_count", 0),
                            },
                        )
                        extract_payload = await asyncio.to_thread(
                            extract_events_from_archive,
                            str(archive_file),
                            ExtractConfig(
                                use_llm=use_llm,
                                use_vision=use_vision,
                                max_chars=max_chars,
                            ),
                        )
                        normalized = await asyncio.to_thread(normalize_events, extract_payload.get("events", []))
                        day_events.extend(normalized)
                        day_articles += int(archive_payload.get("article_count") or 0)
                        day_accounts += int(archive_payload.get("account_count") or 0)
                        day_downloaded += int(archive_payload.get("downloaded_image_count") or 0)
                        day_failed += int(archive_payload.get("failed_image_count") or 0)
                        day_selected += int(extract_payload.get("selected_article_count") or 0)
                        day_extracted += int(extract_payload.get("event_count") or 0)
                        day_outputs = extract_payload.get("outputs", {})

                    all_events.extend(day_events)
                    total_articles += day_articles
                    total_accounts += day_accounts
                    total_downloaded += day_downloaded
                    total_failed += day_failed
                    total_selected += day_selected
                    total_extracted += day_extracted
                    day_payloads.append({
                        "date": date_text,
                        "article_count": day_articles,
                        "account_count": day_accounts,
                        "selected_article_count": day_selected,
                        "event_count": day_extracted,
                        "outputs": day_outputs,
                    })
                    cursor += timedelta(days=1)

                self._set_progress("running", "save", "正在写入活动库并保留收藏状态", 90, {"event_count": len(all_events)})
                saved_count = await asyncio.to_thread(event_store.save_events, all_events)
                cleanup_result = await asyncio.to_thread(event_store.cleanup_duplicate_events)

                discovery_payload = None
                if run_discovery:
                    self._set_progress("running", "discovery", "正在发现新的公众号候选", 94)
                    discovery_payload = await discover_accounts(
                        keywords=parse_keywords(),
                        limit_per_keyword=int(os.getenv("ACCOUNT_DISCOVERY_LIMIT_PER_KEYWORD", "5")),
                        max_results=int(os.getenv("ACCOUNT_DISCOVERY_MAX_RESULTS", "30")),
                        min_score=int(os.getenv("ACCOUNT_DISCOVERY_MIN_SCORE", "35")),
                    )
                    subscribed = subscribe_top_candidates(discovery_payload, discovery_subscribe_top)
                    discovery_payload["subscribed_count"] = len(subscribed)
                    discovery_payload["subscribed"] = subscribed

                result = {
                    "date": end_date.isoformat(),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "lookback_days": lookback_days,
                    "selected_account_count": len(selected_fakeids),
                    "selected_accounts": [
                        {"fakeid": sub.get("fakeid", ""), "nickname": sub.get("nickname", "")}
                        for sub in selected_subs
                    ],
                    "archive": {
                        "article_count": total_articles,
                        "account_count": total_accounts,
                        "downloaded_image_count": total_downloaded,
                        "failed_image_count": total_failed,
                        "days": day_payloads,
                    },
                    "events": {
                        "article_count": total_articles,
                        "selected_article_count": total_selected,
                        "event_count": total_extracted,
                        "saved_count": saved_count,
                        "dedupe": cleanup_result,
                    },
                    "discovery": discovery_payload,
                }
                self._last_run_date = result["date"] or datetime.now(ZoneInfo(self.timezone)).strftime("%Y-%m-%d")
                self._last_run_at = int(time.time())
                self._last_result = result
                self._last_error = ""
                finished_at = int(time.time())
                self._set_progress(
                    "success",
                    "done",
                    "完成：处理文章 %d 篇，抽取活动 %d 个，保存 %d 个" % (
                        total_articles,
                        total_extracted,
                        saved_count,
                    ),
                    100,
                    {
                        "article_count": total_articles,
                        "event_count": total_extracted,
                        "saved_count": saved_count,
                    },
                )
                append_run({
                    "status": "success",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_seconds": max(0, finished_at - started_at),
                    "params": params,
                    "result": result,
                })
                await self._notify_success(result, params, finished_at - started_at)
                await self._notify_upcoming(params)
                return result
            except Exception as exc:
                finished_at = int(time.time())
                self._last_error = str(exc)
                self._set_progress("failed", "failed", str(exc), 100)
                append_run({
                    "status": "failed",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_seconds": max(0, finished_at - started_at),
                    "params": params,
                    "error": str(exc),
                })
                await self._notify_failed(str(exc), params, finished_at - started_at)
                raise

    async def _notify_success(self, result: Dict, params: Dict, duration_seconds: int):
        if not should_notify_automation(params.get("source", "manual")):
            return
        archive = result.get("archive") or {}
        events = result.get("events") or {}
        discovery = result.get("discovery") or {}
        await webhook.notify("event_automation_success", {
            "date": result.get("date", ""),
            "source": params.get("source", "manual"),
            "duration_seconds": max(0, duration_seconds),
            "article_count": archive.get("article_count", 0),
            "selected_article_count": events.get("selected_article_count", 0),
            "event_count": events.get("event_count", 0),
            "saved_count": events.get("saved_count", 0),
            "downloaded_image_count": archive.get("downloaded_image_count", 0),
            "discovered_accounts": discovery.get("candidate_count", 0) if discovery else 0,
            "subscribed_count": discovery.get("subscribed_count", 0) if discovery else 0,
        })

    async def _notify_failed(self, error: str, params: Dict, duration_seconds: int):
        if not should_notify_automation(params.get("source", "manual")):
            return
        await webhook.notify("event_automation_failed", {
            "date": params.get("date") or "today",
            "source": params.get("source", "manual"),
            "duration_seconds": max(0, duration_seconds),
            "error": error,
        })

    async def _notify_upcoming(self, params: Dict):
        if not should_notify_automation(params.get("source", "manual")):
            return
        if not _env_bool("EVENT_UPCOMING_WEBHOOK_ENABLED", True):
            return
        days = int(os.getenv("EVENT_UPCOMING_DAYS", "14"))
        limit = int(os.getenv("EVENT_UPCOMING_LIMIT", "8"))
        events = await asyncio.to_thread(event_store.upcoming_events, days, "confirmed", limit)
        await webhook.notify("event_upcoming_digest", {
            "days": days,
            "event_count": len(events),
            "events": _format_upcoming_events(events, limit),
        })


event_automation = EventAutomation()
