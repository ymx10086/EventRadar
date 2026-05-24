#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVP event extraction pipeline for archived WeChat articles.

Pipeline:
1. Keyword/rule pre-filter.
2. Long article compression around event/date/location/signup evidence.
3. Image text handling: use OCR text when present; optionally ask a multimodal
   MiniMax-compatible model for poster-like images.
4. LLM structured extraction with fallback heuristics.
5. Deduplicate and export JSON/CSV/ICS.
"""

import base64
import csv
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

DEFAULT_EVENTS_DIR = Path(__file__).parent.parent / "data" / "events"
EVENTS_DIR = Path(os.getenv("EVENTS_OUTPUT_DIR", str(DEFAULT_EVENTS_DIR)))

ARCHIVE_ROOT = Path(os.getenv("EVENTRADAR_DATA_DIR", str(Path(__file__).parent.parent / "data")))


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _minimax_base_url() -> str:
    return os.getenv("MINIMAX_BASE_URL", "").rstrip("/")


def _minimax_api_style() -> str:
    return os.getenv("MINIMAX_API_STYLE", "").strip().lower()


def _minimax_model() -> str:
    return os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")


def _minimax_vision_model() -> str:
    return os.getenv("MINIMAX_VISION_MODEL", _minimax_model())


def _minimax_timeout() -> int:
    return _env_int("MINIMAX_TIMEOUT", 90)


def _minimax_api_host() -> str:
    return os.getenv("MINIMAX_API_HOST", "https://api.minimax.io").rstrip("/")

EVENT_KEYWORDS = [
    "活动", "讲座", "论坛", "沙龙", "报名", "招募", "预告", "课程", "培训",
    "竞赛", "比赛", "大赛", "路演", "峰会", "会议", "研讨", "工作坊",
    "开放日", "训练营", "营员", "截止", "直播", "线下", "线上", "参会",
    "黑客松", "编程马拉松",
    "registration", "register", "deadline", "competition", "contest", "event",
    "workshop", "seminar", "forum", "lecture", "webinar", "summit", "hackathon",
]

EVIDENCE_KEYWORDS = [
    "时间", "日期", "地点", "地址", "报名", "扫码", "二维码", "主办", "承办",
    "协办", "嘉宾", "议程", "链接", "截止", "联系人", "参会", "参与",
    "活动", "讲座", "论坛", "沙龙", "会议", "课程", "比赛", "大赛", "黑客松",
    "time", "date", "location", "venue", "register", "registration",
    "deadline", "host", "organizer", "agenda", "scan", "qr",
]

DATE_RE = re.compile(
    r"(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?|"
    r"\d{1,2}[月/-]\d{1,2}日?|"
    r"\d{4}\.\d{1,2}\.\d{1,2}|"
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b)",
    re.IGNORECASE,
)
TIME_RE = re.compile(
    r"(\d{1,2}[:：]\d{2}(?:\s*[-–—~至到]\s*\d{1,2}[:：]\d{2})?|"
    r"\d{1,2}点(?:\d{1,2}分)?(?:\s*[-–—~至到]\s*\d{1,2}点(?:\d{1,2}分)?)?|"
    r"\b\d{1,2}\s*(?:am|pm)\b)",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>\"]+")


@dataclass
class ExtractConfig:
    use_llm: bool = True
    use_vision: Optional[bool] = None
    max_chars: int = 9000
    output_dir: Optional[Path] = None

    def __post_init__(self):
        if self.use_vision is None:
            self.use_vision = _env_bool("MINIMAX_VISION_ENABLED", False)


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(os.getenv("DAILY_ARCHIVE_TIMEZONE", "Asia/Shanghai"))
    except Exception:
        return timezone(timedelta(hours=8))


def _today_str() -> str:
    return datetime.now(_tz()).strftime("%Y-%m-%d")


def _safe_name(value: str, fallback: str = "run") -> str:
    value = (value or "").strip() or fallback
    value = re.sub(r"[\\/:*?\"<>|\s]+", "_", value)
    return value.strip("._")[:80] or fallback


def output_dir_for(date_str: Optional[str] = None, output_dir: Optional[Path] = None) -> Path:
    return (output_dir or EVENTS_DIR) / (date_str or _today_str())


def default_archive_path(date_str: Optional[str] = None) -> Path:
    archive_dir = Path(os.getenv("DAILY_ARCHIVE_DIR", str(ARCHIVE_ROOT / "daily_archives")))
    return archive_dir / (date_str or _today_str()) / "articles.json"


def load_archive(input_path: str) -> Dict:
    path = Path(input_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(f"input JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_articles(archive: Dict) -> List[Dict]:
    result = []
    for account in archive.get("accounts", []):
        for article in account.get("articles", []):
            item = dict(article)
            item.setdefault("account_name", account.get("nickname") or account.get("fakeid") or "")
            item.setdefault("account_alias", account.get("alias", ""))
            result.append(item)
    return result


def _image_text_entries(article: Dict) -> List[Dict]:
    image_text = []
    for img in article.get("images", []):
        ocr = img.get("ocr") or img.get("ocr_text") or img.get("text") or ""
        if ocr:
            image_text.append({
                "source": img.get("source", ""),
                "path": img.get("path") or img.get("relative_path") or "",
                "text": str(ocr)[:2000],
            })
    return image_text


def _combined_article_text(article: Dict, compressed: Optional[Dict] = None) -> str:
    parts = [
        article.get("title", ""),
        article.get("digest", ""),
        article.get("plain_content", ""),
    ]
    for item in _image_text_entries(article):
        parts.append(item.get("text", ""))
    if compressed:
        parts.append(compressed.get("text", ""))
        parts.extend(x.get("text", "") for x in compressed.get("image_ocr", []))
        parts.extend(x.get("text", "") for x in compressed.get("poster_vision", []))
    return "\n".join(str(part or "") for part in parts)


def score_activity_article(article: Dict, compressed: Optional[Dict] = None) -> Tuple[int, List[str]]:
    text = _combined_article_text(article, compressed).lower()
    hits = []
    score = 0
    for keyword in EVENT_KEYWORDS:
        if keyword.lower() in text:
            hits.append(keyword)
            score += 2
    if DATE_RE.search(text):
        hits.append("date")
        score += 2
    if TIME_RE.search(text):
        hits.append("time")
        score += 2
    if "报名" in text or "register" in text or "registration" in text:
        score += 2
    title = article.get("title", "")
    if "活动" in title or "预告" in title:
        score += 2
    if article.get("images") and any(keyword in title for keyword in ["黑客松", "大赛", "比赛", "论坛", "峰会", "开放日", "工作坊"]):
        score += 2
    if compressed and compressed.get("poster_vision"):
        hits.append("vision")
        score += 2
    if any(item.get("text") for item in _image_text_entries(article)):
        hits.append("image_text")
        score += 2
    return score, hits[:20]


def compress_article_text(article: Dict, max_chars: int = 9000) -> Dict:
    title = article.get("title", "")
    plain = article.get("plain_content", "") or ""
    parts = re.split(r"\n{1,}|\r\n|。|；|;|(?<=\.)\s+", plain)
    snippets = []
    seen = set()

    for part in parts:
        p = re.sub(r"\s+", " ", part).strip()
        if not p or p in seen:
            continue
        lower = p.lower()
        keep = (
            DATE_RE.search(p)
            or TIME_RE.search(p)
            or any(k.lower() in lower for k in EVIDENCE_KEYWORDS)
        )
        if keep:
            seen.add(p)
            snippets.append(p)

    if not snippets:
        snippets = [plain[:max_chars]]

    image_text = _image_text_entries(article)

    compressed = "\n".join(snippets)
    if len(compressed) > max_chars:
        compressed = compressed[:max_chars]

    return {
        "title": title,
        "account": article.get("account_name", ""),
        "publish_time": article.get("publish_time_iso") or article.get("publish_time", ""),
        "source_url": article.get("link", ""),
        "text": compressed,
        "image_ocr": image_text,
        "image_paths": [
            img.get("path") for img in article.get("images", [])
            if img.get("path") and img.get("downloaded", True)
        ],
    }


def _minimax_api_key() -> str:
    return os.getenv("MINIMAX_API_KEY", "").strip().strip("'\"")


def _json_from_text(text: str) -> Dict:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


def call_minimax_chat(messages: List[Dict], model: Optional[str] = None,
                      temperature: float = 0.1, max_tokens: int = 4096) -> str:
    api_key = _minimax_api_key()
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured")

    style = _minimax_api_style() or ("anthropic" if api_key.startswith("sk-cp-") else "openai")
    if style == "anthropic":
        return _call_minimax_anthropic(messages, api_key, model, temperature, max_tokens)
    return _call_minimax_openai(messages, api_key, model, temperature, max_tokens)


def _call_minimax_openai(messages: List[Dict], api_key: str, model: Optional[str],
                         temperature: float, max_tokens: int) -> str:
    base_url = (_minimax_base_url() or "https://api.minimax.io/v1").rstrip("/")
    payload = {
        "model": model or _minimax_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=float(_minimax_timeout())) as client:
        resp = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_minimax_anthropic(messages: List[Dict], api_key: str, model: Optional[str],
                            temperature: float, max_tokens: int) -> str:
    base_url = (_minimax_base_url() or "https://api.minimax.io/anthropic").rstrip("/")
    system_prompt = ""
    converted = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            system_prompt = str(content)
            continue
        if isinstance(content, list):
            blocks = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    blocks.append({"type": "text", "text": str(part.get("text", ""))})
                elif part.get("type") == "image_url":
                    image_url = part.get("image_url") or {}
                    data_url = image_url.get("url") or ""
                    match = re.match(r"^data:([^;,]+);base64,(.+)$", data_url, re.DOTALL)
                    if match:
                        blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": match.group(1),
                                "data": match.group(2),
                            },
                        })
                    elif data_url:
                        blocks.append({
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": data_url,
                            },
                        })
            converted.append({
                "role": "assistant" if role == "assistant" else "user",
                "content": blocks or [{"type": "text", "text": ""}],
            })
            continue
        converted.append({
            "role": "assistant" if role == "assistant" else "user",
            "content": [{"type": "text", "text": str(content)}],
        })

    payload = {
        "model": model or _minimax_model(),
        "messages": converted,
        "max_tokens": max_tokens,
        "temperature": max(0.01, temperature),
    }
    if system_prompt:
        payload["system"] = system_prompt
    headers = {"Content-Type": "application/json"}
    if api_key.startswith("sk-cp-"):
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["X-Api-Key"] = api_key
    urls = [f"{base_url}/v1/messages"]
    if api_key.startswith("sk-cp-") and "api.minimax.io" in base_url:
        urls.append("https://api.minimaxi.com/anthropic/v1/messages")

    last_error = None
    with httpx.Client(timeout=float(_minimax_timeout())) as client:
        for url in urls:
            try:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code != 401 or url == urls[-1]:
                    raise
        else:
            raise last_error

    text_parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    return "\n".join(text_parts).strip()


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".gif", ".webp"}:
        return f"image/{suffix[1:]}"
    return "image/jpeg"


def _image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_guess_mime(path)};base64,{encoded}"


def is_poster_like_image(image: Dict, article: Dict) -> bool:
    text = " ".join([article.get("title", ""), image.get("source", ""), image.get("path", "")]).lower()
    return any(k.lower() in text for k in ["cover", "海报", "poster", "报名", "活动", "讲座", "论坛", "大赛", "课程"])


def understand_image_with_minimax_token_plan(image_path: str, prompt: str) -> str:
    api_key = _minimax_api_key()
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured")
    path = Path(image_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        path = (ARCHIVE_ROOT / image_path).resolve()
    if not path.exists():
        return ""

    payload = {
        "prompt": prompt,
        "image_url": _image_data_url(path),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "MM-API-Source": "eventradar",
        "Content-Type": "application/json",
    }
    hosts = [_minimax_api_host()]
    for fallback_host in ("https://api.minimaxi.com", "https://api.minimax.io"):
        if fallback_host not in hosts:
            hosts.append(fallback_host)

    errors = []
    with httpx.Client(timeout=float(_minimax_timeout())) as client:
        for host in hosts:
            try:
                resp = client.post(f"{host}/v1/coding_plan/vlm", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                base_resp = data.get("base_resp") or {}
                status_code = base_resp.get("status_code")
                if base_resp and status_code not in (None, 0):
                    errors.append(f"{host}: {status_code}-{base_resp.get('status_msg')}")
                    continue
                return str(data.get("content") or "").strip()
            except Exception as exc:
                errors.append(f"{host}: {exc}")
    raise RuntimeError("; ".join(errors) or "MiniMax VLM failed")


def recognize_poster_with_minimax(image_path: str, article: Dict) -> str:
    path = Path(image_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        path = (ARCHIVE_ROOT / image_path).resolve()
    if not path.exists():
        return ""

    prompt = (
        "请识别这张微信公众号活动海报中的活动信息。"
        "只返回可见文字摘要，重点包含活动名称、时间、地点、报名方式、主办方。"
        "如果海报里有日期但没有年份，请结合上下文优先使用 2026 年。"
    )
    try:
        return understand_image_with_minimax_token_plan(str(path), prompt)
    except Exception as exc:
        logger.warning("MiniMax Token Plan image understanding failed: %s", exc)

    data_url = _image_data_url(path)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    return call_minimax_chat(messages, model=_minimax_vision_model(), max_tokens=1500)


def enrich_with_poster_vision(article: Dict, compressed: Dict, use_vision: bool) -> Dict:
    if not use_vision:
        compressed["poster_vision"] = []
        return compressed
    if not _minimax_api_key():
        compressed["poster_vision"] = []
        return compressed

    poster_texts = []
    max_images = int(os.getenv("MINIMAX_VISION_MAX_IMAGES", "5"))
    for img in article.get("images", [])[:max_images]:
        if img.get("ocr") or img.get("ocr_text"):
            continue
        path = img.get("path")
        if not path:
            continue
        try:
            text = recognize_poster_with_minimax(path, article)
            if text and not _looks_like_vision_refusal(text):
                poster_texts.append({"path": path, "text": text[:3000]})
        except Exception as exc:
            logger.warning("MiniMax poster recognition failed: %s", exc)
    compressed["poster_vision"] = poster_texts
    return compressed


def _looks_like_vision_refusal(text: str) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return False
    return bool(re.search(
        r"无法(?:直接)?(?:查看|读取|处理|识别)图片|"
        r"不能(?:直接)?(?:查看|读取|处理|识别)图片|"
        r"请(?:您)?(?:上传|提供|发送).{0,20}(?:图片|海报)|"
        r"unable to (?:view|read|access|process) (?:the )?image|"
        r"can't (?:view|read|access|process) (?:the )?image",
        cleaned,
        re.IGNORECASE,
    ))


def _event_has_actionable_time(raw: Dict) -> bool:
    fields = [
        raw.get("start_time"),
        raw.get("end_time"),
        raw.get("signup_start_time"),
        raw.get("registration_start_time"),
        raw.get("registration_time"),
        raw.get("signup_deadline"),
        raw.get("registration_deadline"),
        raw.get("evidence"),
        raw.get("description"),
    ]
    text = " ".join(str(value or "") for value in fields)
    return bool(DATE_RE.search(text))


def _is_valid_raw_event(raw: Dict) -> bool:
    if not isinstance(raw, dict):
        return False
    combined = " ".join(str(raw.get(field) or "") for field in (
        "title", "start_time", "end_time", "location", "organizer",
        "signup_deadline", "signup_start_time", "description", "evidence",
    ))
    if _looks_like_vision_refusal(combined):
        return False
    if not str(raw.get("title") or "").strip():
        return False
    return _event_has_actionable_time(raw)


def _system_prompt() -> str:
    return (
        "你是活动信息抽取器。请从微信公众号文章片段中抽取结构化活动。"
        "一篇文章可能包含多个活动。只输出 JSON，不要解释。"
        "如果不是活动或信息不足，输出 {\"events\": []}。"
        "字段：title, start_time, end_time, location, organizer, signup_deadline, "
        "signup_start_time, signup_url, description, category, confidence, evidence。"
        "时间尽量使用 ISO 8601；无法确定年份时参考文章发布时间；未知字段用空字符串。"
        "如果报名开始/报名截止早于活动开始，也必须保留这些关键时间，便于日历优先显示最早行动时间。"
    )


def extract_with_llm(compressed: Dict) -> List[Dict]:
    user_payload = json.dumps(compressed, ensure_ascii=False)
    content = call_minimax_chat(
        [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_payload},
        ],
        max_tokens=4096,
    )
    data = _json_from_text(content)
    events = data.get("events", [])
    return events if isinstance(events, list) else []


def fallback_extract(compressed: Dict) -> List[Dict]:
    text = "\n".join([
        compressed.get("title", ""),
        compressed.get("text", ""),
        "\n".join([x.get("text", "") for x in compressed.get("image_ocr", [])]),
        "\n".join([x.get("text", "") for x in compressed.get("poster_vision", [])]),
    ])
    lower = text.lower()
    if not any(k.lower() in lower for k in EVENT_KEYWORDS):
        return []

    date_match = DATE_RE.search(text)
    time_match = TIME_RE.search(text)
    location = _extract_after_labels(text, ["上课地点", "活动地点", "会议地点", "举办地点", "地点", "地址", "Location", "Venue"])
    organizer = _extract_after_labels(text, ["主办方", "主办单位", "主办", "Organizer", "Host"])
    signup_start = _extract_after_labels(text, ["报名开始", "报名时间", "报名日期", "报名开放", "开放报名", "Registration Opens"])
    deadline = _extract_after_labels(text, ["报名截止", "截止时间", "Deadline"])
    url_match = URL_RE.search(text)

    title = compressed.get("title", "")
    event = {
        "title": title,
        "start_time": " ".join([m.group(0) for m in [date_match, time_match] if m]).strip(),
        "end_time": "",
        "location": location,
        "organizer": organizer,
        "signup_start_time": signup_start,
        "signup_deadline": deadline,
        "signup_url": url_match.group(0) if url_match else "",
        "description": _shorten(text, 800),
        "category": _classify_event(text),
        "confidence": 0.45 if date_match or time_match else 0.3,
        "evidence": _shorten(compressed.get("text", ""), 500),
    }
    return [event]


def supplement_events_with_fallback(raw_events: List[Dict], fallback_events: List[Dict]) -> List[Dict]:
    """Fill obvious missing fields in LLM output with deterministic label matches."""
    if not raw_events or not fallback_events:
        return raw_events

    fallback = fallback_events[0]
    fill_fields = [
        "start_time",
        "end_time",
        "location",
        "organizer",
        "signup_start_time",
        "signup_deadline",
        "signup_url",
        "category",
        "evidence",
    ]
    merged = []
    for raw in raw_events:
        item = dict(raw)
        for field in fill_fields:
            if not str(item.get(field) or "").strip() and fallback.get(field):
                item[field] = fallback[field]
        merged.append(item)
    return merged


def _extract_after_labels(text: str, labels: List[str]) -> str:
    for label in labels:
        pattern = re.compile(rf"[【\[]?{re.escape(label)}[】\]]?\s*[:：]?\s*([^\n。；;]{{2,80}})", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return re.sub(r"^[】\]：:\s]+", "", match.group(1)).strip()
    return ""


def _shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]


def _classify_event(text: str) -> str:
    checks = [
        ("competition", ["大赛", "竞赛", "比赛", "competition", "contest"]),
        ("lecture", ["讲座", "课程", "lecture", "class"]),
        ("forum", ["论坛", "峰会", "forum", "summit"]),
        ("workshop", ["工作坊", "培训", "workshop", "training"]),
        ("recruiting", ["招募", "报名", "registration"]),
    ]
    lower = text.lower()
    for category, keywords in checks:
        if any(k.lower() in lower for k in keywords):
            return category
    return "event"


def normalize_event(raw: Dict, article: Dict, method: str) -> Dict:
    title = str(raw.get("title") or article.get("title") or "").strip()
    event_id_seed = "|".join([
        title.lower(),
        str(raw.get("start_time") or ""),
        str(raw.get("location") or ""),
        article.get("link", ""),
    ])
    image_paths = [
        img.get("path") for img in article.get("images", [])
        if img.get("path") and img.get("downloaded", True)
    ]
    event = {
        "id": hashlib.sha1(event_id_seed.encode("utf-8")).hexdigest()[:16],
        "title": title,
        "account": article.get("account_name", ""),
        "source_article_title": article.get("title", ""),
        "source_article_url": article.get("link", ""),
        "source_publish_time": article.get("publish_time_iso") or article.get("publish_time", ""),
        "start_time": str(raw.get("start_time") or ""),
        "end_time": str(raw.get("end_time") or ""),
        "location": str(raw.get("location") or ""),
        "organizer": str(raw.get("organizer") or ""),
        "signup_start_time": str(raw.get("signup_start_time") or raw.get("registration_start_time") or raw.get("signup_time") or raw.get("registration_time") or ""),
        "signup_deadline": str(raw.get("signup_deadline") or ""),
        "signup_url": str(raw.get("signup_url") or ""),
        "description": str(raw.get("description") or ""),
        "category": str(raw.get("category") or "event"),
        "confidence": _normalize_confidence(raw.get("confidence")),
        "evidence": str(raw.get("evidence") or "")[:1000],
        "image_paths": image_paths,
        "extraction_method": method,
    }
    calendar_time, calendar_label = calendar_time_for_event(event)
    event["calendar_time"] = calendar_time
    event["calendar_time_label"] = calendar_label
    return event


def _normalize_confidence(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().lower()
    mapping = {
        "high": 0.9,
        "medium": 0.6,
        "low": 0.3,
        "高": 0.9,
        "中": 0.6,
        "低": 0.3,
    }
    if text in mapping:
        return mapping[text]
    try:
        return float(text)
    except ValueError:
        return 0.0


def dedupe_events(events: List[Dict]) -> List[Dict]:
    seen = {}
    for event in events:
        key = "|".join([
            re.sub(r"\s+", "", event.get("title", "")).lower(),
            event.get("start_time", ""),
            re.sub(r"\s+", "", event.get("location", "")).lower(),
        ])
        if not key.strip("|"):
            key = event.get("id", "")
        old = seen.get(key)
        if old is None or event.get("confidence", 0) > old.get("confidence", 0):
            seen[key] = event
    return sorted(seen.values(), key=lambda e: (e.get("calendar_time") or e.get("start_time") or "9999", e.get("title", "")))


def extract_events_from_archive(input_path: str, config: Optional[ExtractConfig] = None) -> Dict:
    config = config or ExtractConfig()
    archive = load_archive(input_path)
    articles = iter_articles(archive)
    selected = []
    events = []
    skipped = []
    llm_available = bool(_minimax_api_key())

    for article in articles:
        compressed = compress_article_text(article, max_chars=config.max_chars)
        score, hits = score_activity_article(article, compressed)
        if config.use_vision and article.get("images"):
            compressed = enrich_with_poster_vision(article, compressed, config.use_vision)
            score, hits = score_activity_article(article, compressed)
        if score < int(os.getenv("EVENT_PREFILTER_MIN_SCORE", "4")):
            skipped.append({"title": article.get("title", ""), "score": score})
            continue

        selected.append({"title": article.get("title", ""), "score": score, "hits": hits})

        method = "fallback"
        raw_events = []
        if config.use_llm and llm_available:
            try:
                raw_events = extract_with_llm(compressed)
                fallback_events = fallback_extract(compressed)
                raw_events = supplement_events_with_fallback(raw_events, fallback_events)
                raw_events = [raw for raw in raw_events if _is_valid_raw_event(raw)]
                method = "minimax"
            except Exception as exc:
                logger.warning("MiniMax extraction failed, fallback used: %s", exc)
        if not raw_events:
            raw_events = [raw for raw in fallback_extract(compressed) if _is_valid_raw_event(raw)]

        for raw in raw_events:
            events.append(normalize_event(raw, article, method))

    deduped = dedupe_events(events)
    date_str = archive.get("date") or _safe_name(Path(input_path).parent.name)
    out_dir = output_dir_for(date_str, config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "source_file": str(Path(input_path).resolve()),
        "date": date_str,
        "generated_at": int(time.time()),
        "generated_at_iso": datetime.now(_tz()).isoformat(),
        "llm_enabled": bool(config.use_llm),
        "llm_available": llm_available,
        "vision_enabled": bool(config.use_vision),
        "article_count": len(articles),
        "selected_article_count": len(selected),
        "event_count": len(deduped),
        "selected_articles": selected,
        "events": deduped,
    }

    json_path = out_dir / "events.json"
    csv_path = out_dir / "events.csv"
    ics_path = out_dir / "calendar.ics"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_events_csv(deduped, csv_path)
    write_events_ics(deduped, ics_path)

    payload["outputs"] = {
        "events_json": str(json_path),
        "events_csv": str(csv_path),
        "calendar_ics": str(ics_path),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def write_events_csv(events: List[Dict], path: Path):
    fields = [
        "id", "title", "account", "start_time", "end_time", "location", "organizer",
        "signup_deadline", "signup_url", "category", "confidence",
        "source_article_title", "source_article_url", "image_paths",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for event in events:
            row = {k: event.get(k, "") for k in fields}
            row["image_paths"] = "\n".join(event.get("image_paths", []))
            writer.writerow(row)


def _ics_escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _clean_time_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(
        r"^(报名开始|报名时间|报名日期|报名开放|开放报名|报名截止|截止时间|活动时间|时间|日期|Deadline|Registration Opens)\s*[:：]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    match = re.search(
        r"\d{4}[-/年]\s*\d{1,2}[-/月]\s*\d{1,2}(?:日)?"
        r"(?:(?:[T\s]*)\d{1,2}[:：点]\d{0,2}(?::\d{2})?(?:\s*(?:Z|[+-]\d{2}:?\d{2}))?)?",
        text,
    )
    if match:
        return match.group(0).strip()
    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}(?:,?\s*\d{1,2}[:：]\d{2})?",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(0).strip().rstrip(".")
    return text


def _date_from_match(match: re.Match) -> str:
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def _looks_like_eligibility_date(label: str, value: str, event: Dict) -> bool:
    if label != "活动开始" or not value:
        return False
    value_text = str(value or "")
    context = " ".join([
        value_text,
        str(event.get("evidence") or ""),
        str(event.get("reason") or ""),
        str(event.get("note") or ""),
        str(event.get("description") or ""),
    ])
    escaped = re.escape(value_text).replace("\\ ", r"\s+")
    match = re.search(rf"(.{{0,80}}{escaped}.{{0,80}})", context, re.IGNORECASE)
    window = match.group(1) if match else context[:240]
    return bool(re.search(
        r"born\s+(?:after|before)|aged?\s+\d|age\s+limit|years?\s+old|"
        r"年龄|出生|周岁|不超过|以下|以上|企业注册|工商注册|成立时间|注册时间",
        window,
        re.IGNORECASE,
    ))


def _explicit_deadline_date(event: Dict) -> str:
    fields = [
        event.get("signup_deadline") or event.get("registration_deadline") or "",
        event.get("evidence") or "",
        event.get("reason") or "",
        event.get("note") or "",
        event.get("description") or "",
        event.get("raw_json") or "",
    ]
    labeled_patterns = [
        r"(?:报名截止|截止时间|投递截止时间|申报截止|提交截止|截止日期|Deadline)[^\n。；;]{0,80}?(\d{4})[-/年]\s*(\d{1,2})[-/月]\s*(\d{1,2})(?:日)?",
        r"(?:报名截止|截止时间|投递截止时间|申报截止|提交截止|截止日期|Deadline)[^\n。；;]{0,80}?\b(\d{4})-(\d{1,2})-(\d{1,2})T?0?0:00",
    ]
    for field in fields:
        text = str(field or "")
        for pattern in labeled_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return _date_from_match(match)

    deadline = str(event.get("signup_deadline") or event.get("registration_deadline") or "")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        cleaned = re.sub(r",?\s*\d{1,2}[:：]\d{2}.*$", "", deadline.strip().rstrip("."), flags=re.IGNORECASE)
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    match = re.search(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:T|\s)?", deadline)
    if match:
        return _date_from_match(match)
    match = re.search(r"(\d{4})[年/-]\s*(\d{1,2})[月/-]\s*(\d{1,2})(?:日)?", deadline)
    if match:
        return _date_from_match(match)
    return ""


def _parse_event_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    v = _clean_time_text(value).replace("：", ":")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%Z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日%H:%M",
        "%B %d, %Y, %H:%M",
        "%B %d, %Y %H:%M",
        "%b %d, %Y, %H:%M",
        "%b %d, %Y %H:%M",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y年%m月%d日",
    ):
        try:
            dt = datetime.strptime(v, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz())
            return dt
        except ValueError:
            continue
    match = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?.*?(\d{1,2})[:：点](\d{2})?", v)
    if match:
        minute = int(match.group(5) or 0)
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                            int(match.group(4)), minute, tzinfo=_tz())
        except ValueError:
            return None
    match = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?", v)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=_tz())
        except ValueError:
            return None
    return None


def _context_year(event: Dict) -> int:
    fields = [
        event.get("source_publish_time") or "",
        event.get("source_publish_time_iso") or "",
        event.get("source_article_title") or "",
        event.get("title") or "",
        event.get("description") or "",
        event.get("evidence") or "",
        event.get("raw_json") or "",
    ]
    for field in fields:
        match = re.search(r"\b(20\d{2})\b", str(field or ""))
        if match:
            return int(match.group(1))
    return datetime.now(_tz()).year


def _fill_missing_year(value: str, event: Dict) -> str:
    text = str(value or "").strip()
    if not text or re.search(r"\b\d{4}\b", text):
        return text
    year = _context_year(event)
    match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日?(.*)$", text)
    if match:
        return f"{year}年{int(match.group(1))}月{int(match.group(2))}日{match.group(3).strip()}"
    match = re.search(r"(\d{1,2})[/-](\d{1,2})(.*)$", text)
    if match:
        return f"{year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}{match.group(3).strip()}"
    return text


def calendar_time_for_event(event: Dict) -> Tuple[str, str]:
    candidates = [
        ("报名开始", event.get("signup_start_time") or event.get("registration_start_time") or event.get("registration_time")),
        ("报名截止", _explicit_deadline_date(event) or event.get("signup_deadline") or event.get("registration_deadline")),
        ("活动开始", event.get("start_time")),
    ]
    parsed = []
    for label, value in candidates:
        text = _clean_time_text(str(value or ""))
        text = _fill_missing_year(text, event)
        if _looks_like_eligibility_date(label, text, event):
            continue
        dt = _parse_event_datetime(text)
        if dt:
            parsed.append((dt, text, label))
    if not parsed:
        return str(event.get("start_time") or ""), "活动开始"
    parsed.sort(key=lambda item: item[0])
    return parsed[0][1], parsed[0][2]


def _is_date_only(value: str) -> bool:
    if not value:
        return False
    v = value.strip()
    date_patterns = (
        r"^\d{4}-\d{1,2}-\d{1,2}$",
        r"^\d{4}/\d{1,2}/\d{1,2}$",
        r"^\d{4}年\s*\d{1,2}月\s*\d{1,2}日$",
    )
    return any(re.match(pattern, v) for pattern in date_patterns)


def build_events_ics(events: List[Dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EventRadar//Events//CN",
        "CALSCALE:GREGORIAN",
    ]
    for event in events:
        calendar_time, calendar_label = calendar_time_for_event(event)
        start_value = calendar_time or event.get("start_time", "")
        start = _parse_event_datetime(start_value)
        end = _parse_event_datetime(event.get("end_time", "")) if calendar_label == "活动开始" else None
        if start is None:
            continue
        start_is_date_only = _is_date_only(start_value)
        end_is_date_only = _is_date_only(event.get("end_time", ""))
        if end is None and start_is_date_only:
            end = start + timedelta(days=1)
            end_is_date_only = True
        elif end is None:
            end = start + timedelta(hours=2)
        elif start_is_date_only and end_is_date_only and end <= start:
            end = start + timedelta(days=1)
        if start_is_date_only and end_is_date_only:
            start_line = f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}"
            end_line = f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}"
        else:
            start_line = f"DTSTART:{start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            end_line = f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        description_parts = [
            f"日历时间类型：{calendar_label}",
            f"活动时间：{event.get('start_time', '')}",
            f"报名开始：{event.get('signup_start_time') or event.get('registration_start_time') or ''}",
            f"报名截止：{event.get('signup_deadline') or event.get('registration_deadline') or ''}",
            event.get("description") or "",
            event.get("source_article_url") or event.get("source_url") or "",
        ]
        description = "\n".join(part for part in description_parts if str(part).strip())
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{event.get('id')}@eventradar",
            f"DTSTAMP:{now}",
            start_line,
            end_line,
            f"SUMMARY:{_ics_escape(event.get('title', ''))}",
            f"LOCATION:{_ics_escape(event.get('location', ''))}",
            f"DESCRIPTION:{_ics_escape(description)}",
            f"URL:{event.get('source_article_url', '')}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def write_events_ics(events: List[Dict], path: Path):
    path.write_text(build_events_ics(events), encoding="utf-8")
