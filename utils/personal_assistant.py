#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personal activity assistant configuration and event normalization helpers.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from utils import rss_store
from utils.event_extractor import clean_location_value


DATA_DIR = Path(os.getenv("PERSONAL_ASSISTANT_DIR", str(Path(__file__).parent.parent / "data" / "personal_assistant")))
PROFILE_FILE = DATA_DIR / "profile.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LINK_SOURCES_FILE = DATA_DIR / "link_sources.json"


DEFAULT_PROFILE = {
    "identity": "学生",
    "profession": "",
    "research_direction": "",
    "interests": ["创新创业", "AI", "竞赛", "讲座"],
    "priority_keywords": ["创新创业", "AI", "人工智能", "创业", "竞赛", "路演", "报名"],
    "avoid_topics": [],
}

DEFAULT_SETTINGS = {
    "daily_fetch_enabled": False,
    "daily_fetch_time": "07:30",
    "daily_fetch_lookback_days": 0,
    "event_retention_days": 15,
    "auto_import_calendar": True,
    "use_llm": True,
    "use_vision": True,
    "download_images": True,
    "max_chars": 9000,
    "wechat_fetch_concurrency": 1,
    "wechat_fetch_delay_min": 8,
    "wechat_fetch_delay_max": 18,
    "wechat_account_delay": 20,
    "wechat_max_articles_per_account": 10,
    "wechat_verification_pause_minutes": 60,
    "wechat_verification_stop_threshold": 1,
    "wechat_proxy_required": False,
}


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default):
    _ensure_dir()
    if not path.exists():
        _write_json(path, default)
        return json.loads(json.dumps(default, ensure_ascii=False))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(json.dumps(default, ensure_ascii=False))


def _write_json(path: Path, payload):
    _ensure_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_profile() -> Dict:
    profile = _read_json(PROFILE_FILE, DEFAULT_PROFILE)
    merged = {**DEFAULT_PROFILE, **profile}
    for key in ["interests", "priority_keywords", "avoid_topics"]:
        value = merged.get(key)
        if isinstance(value, str):
            merged[key] = [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        elif not isinstance(value, list):
            merged[key] = []
    return merged


def save_profile(profile: Dict) -> Dict:
    current = get_profile()
    current.update({k: v for k, v in profile.items() if k in DEFAULT_PROFILE})
    _write_json(PROFILE_FILE, current)
    return get_profile()


def get_settings() -> Dict:
    settings = _read_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    merged = {**DEFAULT_SETTINGS, **settings}
    try:
        merged["max_chars"] = int(merged.get("max_chars") or DEFAULT_SETTINGS["max_chars"])
    except (TypeError, ValueError):
        merged["max_chars"] = DEFAULT_SETTINGS["max_chars"]
    try:
        merged["daily_fetch_lookback_days"] = max(0, min(30, int(merged.get("daily_fetch_lookback_days") or 0)))
    except (TypeError, ValueError):
        merged["daily_fetch_lookback_days"] = 0
    try:
        merged["event_retention_days"] = max(1, min(365, int(merged.get("event_retention_days") or 15)))
    except (TypeError, ValueError):
        merged["event_retention_days"] = 15
    int_bounds = {
        "wechat_fetch_concurrency": (1, 5, 1),
        "wechat_max_articles_per_account": (1, 100, 10),
        "wechat_verification_pause_minutes": (0, 720, 60),
        "wechat_verification_stop_threshold": (1, 20, 1),
    }
    for key, (low, high, default) in int_bounds.items():
        try:
            merged[key] = max(low, min(high, int(merged.get(key, default))))
        except (TypeError, ValueError):
            merged[key] = default
    float_bounds = {
        "wechat_fetch_delay_min": (0, 300, 8.0),
        "wechat_fetch_delay_max": (0, 300, 18.0),
        "wechat_account_delay": (0, 600, 20.0),
    }
    for key, (low, high, default) in float_bounds.items():
        try:
            merged[key] = max(low, min(high, float(merged.get(key, default))))
        except (TypeError, ValueError):
            merged[key] = default
    if merged["wechat_fetch_delay_max"] < merged["wechat_fetch_delay_min"]:
        merged["wechat_fetch_delay_max"] = merged["wechat_fetch_delay_min"]
    merged["wechat_proxy_required"] = bool(merged.get("wechat_proxy_required", False))
    return merged


def save_settings(settings: Dict) -> Dict:
    current = get_settings()
    for key in DEFAULT_SETTINGS:
        if key in settings:
            current[key] = settings[key]
    _write_json(SETTINGS_FILE, current)
    return get_settings()


def _read_link_sources() -> List[Dict]:
    payload = _read_json(LINK_SOURCES_FILE, {"sources": []})
    sources = payload.get("sources", [])
    return sources if isinstance(sources, list) else []


def _write_link_sources(sources: List[Dict]):
    _write_json(LINK_SOURCES_FILE, {"sources": sources})


def list_sources() -> List[Dict]:
    sources = []
    for sub in rss_store.list_subscriptions():
        sources.append({
            "id": "wechat:" + sub["fakeid"],
            "source_type": "wechat",
            "fakeid": sub["fakeid"],
            "name": sub.get("nickname") or sub["fakeid"],
            "alias": sub.get("alias", ""),
            "url": "",
            "enabled": True,
            "auto_fetch": True,
            "article_count": sub.get("article_count", 0),
            "created_at": sub.get("created_at", 0),
            "last_poll": sub.get("last_poll", 0),
        })
    sources.extend(_read_link_sources())
    return sources


def add_source(payload: Dict) -> Dict:
    source_type = str(payload.get("source_type") or "link").lower()
    now = int(time.time())
    if source_type == "wechat":
        fakeid = str(payload.get("fakeid") or "").strip()
        if not fakeid:
            raise ValueError("fakeid is required for wechat source")
        rss_store.add_subscription(
            fakeid=fakeid,
            nickname=str(payload.get("name") or payload.get("nickname") or fakeid),
            alias=str(payload.get("alias") or ""),
            head_img=str(payload.get("head_img") or ""),
        )
        return next(item for item in list_sources() if item["id"] == "wechat:" + fakeid)

    name = str(payload.get("name") or payload.get("url") or "未命名链接源").strip()
    url = str(payload.get("url") or "").strip()
    if not url:
        raise ValueError("url is required for link source")
    source_id = payload.get("id") or "link:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    sources = [item for item in _read_link_sources() if item.get("id") != source_id]
    item = {
        "id": source_id,
        "source_type": "link",
        "name": name,
        "url": url,
        "enabled": bool(payload.get("enabled", True)),
        "auto_fetch": bool(payload.get("auto_fetch", True)),
        "created_at": now,
        "last_poll": 0,
    }
    sources.append(item)
    _write_link_sources(sources)
    return item


def update_source(source_id: str, updates: Dict) -> Optional[Dict]:
    if source_id.startswith("wechat:"):
        item = next((src for src in list_sources() if src["id"] == source_id), None)
        if not item:
            return None
        if "auto_fetch" in updates:
            rss_store.update_subscription_auto_fetch(source_id.split(":", 1)[1], bool(updates["auto_fetch"]))
        item = next((src for src in list_sources() if src["id"] == source_id), item)
        return {**item, **{k: updates[k] for k in ["enabled"] if k in updates}}

    sources = _read_link_sources()
    found = None
    for item in sources:
        if item.get("id") == source_id:
            for key in ["name", "url", "enabled", "auto_fetch"]:
                if key in updates:
                    item[key] = updates[key]
            found = item
            break
    if found:
        _write_link_sources(sources)
    return found


def delete_source(source_id: str) -> bool:
    if source_id.startswith("wechat:"):
        return rss_store.remove_subscription(source_id.split(":", 1)[1])
    sources = _read_link_sources()
    kept = [item for item in sources if item.get("id") != source_id]
    if len(kept) == len(sources):
        return False
    _write_link_sources(kept)
    return True


def _keywords(profile: Dict) -> Dict[str, List[str]]:
    positive = []
    for key in ["research_direction", "interests", "priority_keywords"]:
        value = profile.get(key)
        if isinstance(value, list):
            positive.extend(str(item).strip() for item in value if str(item).strip())
        elif str(value or "").strip():
            positive.append(str(value).strip())
    negative = [str(item).strip() for item in profile.get("avoid_topics", []) if str(item).strip()]
    return {"positive": positive, "negative": negative}


def grade_event(event: Dict, profile: Optional[Dict] = None) -> Dict:
    profile = profile or get_profile()
    words = _keywords(profile)
    text = " ".join([
        str(event.get("title") or ""),
        str(event.get("description") or ""),
        str(event.get("category") or ""),
        " ".join(event.get("tags") or []),
        str(event.get("organizer") or ""),
    ]).lower()
    positive_hits = [word for word in words["positive"] if word and word.lower() in text]
    negative_hits = [word for word in words["negative"] if word and word.lower() in text]

    score = 0
    score += min(55, len(set(positive_hits)) * 18)
    if event.get("signup_deadline") or event.get("registration_deadline"):
        score += 10
    if event.get("location"):
        score += 8
    if event.get("confidence"):
        try:
            score += float(event.get("confidence")) * 20
        except (TypeError, ValueError):
            pass
    if negative_hits:
        score -= 45

    if score >= 76:
        level = "S"
        label = "强相关"
    elif score >= 56:
        level = "A"
        label = "值得关注"
    elif score >= 34:
        level = "B"
        label = "一般相关"
    else:
        level = "C"
        label = "低相关"

    reason_parts = []
    if positive_hits:
        reason_parts.append("匹配画像关键词：" + "、".join(sorted(set(positive_hits))[:4]))
    if negative_hits:
        reason_parts.append("包含避免主题：" + "、".join(sorted(set(negative_hits))[:3]))
    if event.get("signup_deadline") or event.get("registration_deadline"):
        reason_parts.append("包含报名截止信息")
    if event.get("location"):
        reason_parts.append("包含明确地点")
    if not reason_parts:
        reason_parts.append("与当前画像关键词匹配较少")

    return {
        "level": level,
        "priority": level,
        "reason": f"{label}：" + "；".join(reason_parts),
    }


def normalize_event(event: Dict, profile: Optional[Dict] = None) -> Dict:
    tags = event.get("tags")
    if not tags:
        category = event.get("category") or "event"
        tags = [category] if category else []
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.replace("，", ",").split(",") if item.strip()]

    grade = {
        "level": event.get("level") or event.get("priority") or "B",
        "priority": event.get("priority") or event.get("level") or "B",
        "reason": event.get("reason") or event.get("note") or event.get("evidence") or "",
    }
    if not grade["reason"] or not event.get("level"):
        grade = grade_event({**event, "tags": tags}, profile)

    source_name = event.get("source_name") or event.get("account") or event.get("source_article_title") or ""
    source_url = event.get("source_url") or event.get("source_article_url") or event.get("signup_url") or ""
    source_type = event.get("source_type") or ("wechat" if event.get("account") or event.get("source_article_url") else "manual")

    created_at = event.get("created_at")
    if isinstance(created_at, int):
        created_at_value = created_at
    else:
        created_at_value = int(time.time()) if not created_at else created_at

    normalized = {
        **event,
        "title": event.get("title", ""),
        "start_time": event.get("start_time", ""),
        "end_time": event.get("end_time", ""),
        "signup_start_time": event.get("signup_start_time", ""),
        "calendar_time": event.get("calendar_time", ""),
        "calendar_time_label": event.get("calendar_time_label", ""),
        "location": clean_location_value(event.get("location", "")),
        "city": event.get("city", ""),
        "organizer": event.get("organizer", ""),
        "description": event.get("description", ""),
        "registration_deadline": event.get("registration_deadline") or event.get("signup_deadline", ""),
        "registration_link": event.get("registration_link") or event.get("signup_url", ""),
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "tags": tags,
        "level": grade["level"],
        "priority": grade["priority"],
        "reason": grade["reason"],
        "status": event.get("status") or "pending",
        "is_favorite": bool(event.get("is_favorite") or event.get("favorite")),
        "favorite": bool(event.get("is_favorite") or event.get("favorite")),
        "created_at": created_at_value,
    }
    normalized["signup_deadline"] = normalized["registration_deadline"]
    normalized["signup_url"] = normalized["registration_link"]
    normalized["category"] = normalized.get("category") or (tags[0] if tags else "event")
    normalized["account"] = normalized.get("account") or source_name
    normalized["note"] = normalized.get("note") or normalized["reason"]
    try:
        from utils.event_extractor import calendar_time_for_event

        calendar_time, calendar_label = calendar_time_for_event(normalized)
        normalized["calendar_time"] = calendar_time
        normalized["calendar_time_label"] = calendar_label
    except Exception:
        normalized["calendar_time"] = normalized.get("calendar_time") or normalized.get("start_time", "")
        normalized["calendar_time_label"] = normalized.get("calendar_time_label") or "活动开始"
    return normalized


def normalize_events(events: List[Dict]) -> List[Dict]:
    profile = get_profile()
    return [normalize_event(event, profile) for event in events]
