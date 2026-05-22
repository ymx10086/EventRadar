#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily archive for subscribed WeChat accounts.

It exports articles already cached by the RSS poller into one JSON file per day
and downloads article images to local paths recorded in that JSON.
"""

import hashlib
import json
import logging
import mimetypes
import os
import re
import time
from datetime import datetime, date, time as dt_time, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlparse

from bs4 import BeautifulSoup

from utils import rss_store

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_DIR = Path(__file__).parent.parent / "data" / "daily_archives"
ARCHIVE_DIR = Path(os.getenv("DAILY_ARCHIVE_DIR", str(DEFAULT_ARCHIVE_DIR)))
ARCHIVE_TIMEZONE = os.getenv("DAILY_ARCHIVE_TIMEZONE", "Asia/Shanghai")


def _get_timezone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(ARCHIVE_TIMEZONE)
    except Exception:
        logger.warning("Invalid timezone %s, fallback to UTC+8", ARCHIVE_TIMEZONE)
        return timezone(timedelta(hours=8))


def _current_date_string() -> str:
    return datetime.now(_get_timezone()).strftime("%Y-%m-%d")


def _parse_date(date_str: Optional[str]) -> date:
    if not date_str:
        date_str = _current_date_string()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc


def _day_bounds(target_date: date) -> Tuple[int, int]:
    tz = _get_timezone()
    start = datetime.combine(target_date, dt_time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def get_archive_dir(date_str: Optional[str] = None) -> Path:
    target_date = _parse_date(date_str)
    return ARCHIVE_DIR / target_date.strftime("%Y-%m-%d")


def get_archive_file(date_str: Optional[str] = None) -> Path:
    return get_archive_dir(date_str) / "articles.json"


def _safe_name(value: str, fallback: str = "item") -> str:
    value = (value or "").strip()
    if not value:
        value = fallback
    value = re.sub(r"[\\/:*?\"<>|\s]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    return value[:80] or fallback


def _decode_proxy_image_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    proxied = query.get("url")
    if proxied:
        return unquote(proxied[0])
    return url


def _is_downloadable_image_url(url: str) -> bool:
    if not url or url.startswith("data:"):
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def extract_article_image_urls(article: Dict) -> List[Dict]:
    """Extract cover and content image URLs in stable order."""
    images: List[Dict] = []
    seen = set()

    def add(url: str, source: str):
        original = _decode_proxy_image_url(url or "")
        if not _is_downloadable_image_url(original) or original in seen:
            return
        seen.add(original)
        images.append({"source": source, "url": original})

    add(article.get("cover", ""), "cover")

    content = article.get("content", "") or ""
    if content:
        soup = BeautifulSoup(content, "html.parser")
        for img in soup.find_all("img"):
            add(img.get("data-src") or img.get("src") or "", "content")

    return images


def _extension_from_url(url: str, content_type: str = "") -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ".jpg" if ext == ".jpe" else ext

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("wx_fmt", "tp"):
        fmt = (query.get(key) or [""])[0].lower().strip(".")
        if fmt:
            if fmt == "jpeg":
                fmt = "jpg"
            if re.fullmatch(r"[a-z0-9]+", fmt):
                return f".{fmt}"

    suffix = Path(parsed.path).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    return ".jpg"


def _download_url(url: str, timeout: int = 30) -> Tuple[bytes, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mp.weixin.qq.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        from curl_cffi.requests import Session as CurlSession

        with CurlSession(impersonate="chrome120") as session:
            resp = session.get(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "")
    except ImportError:
        import httpx

        with httpx.Client(timeout=float(timeout), follow_redirects=True, verify=False) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "")


def _download_image(url: str, target_dir: Path, index: int, force: bool = False) -> Dict:
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    target_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(target_dir.glob(f"{index:03d}_{url_hash}.*"))
    if existing and not force:
        path = existing[0]
        return {
            "url": url,
            "path": str(path),
            "relative_path": str(path.relative_to(ARCHIVE_DIR.parent)),
            "downloaded": True,
            "skipped_existing": True,
            "error": "",
        }

    content, content_type = _download_url(url)
    ext = _extension_from_url(url, content_type)
    path = target_dir / f"{index:03d}_{url_hash}{ext}"
    path.write_bytes(content)

    return {
        "url": url,
        "path": str(path),
        "relative_path": str(path.relative_to(ARCHIVE_DIR.parent)),
        "downloaded": True,
        "skipped_existing": False,
        "error": "",
    }


def _serialize_article(
    article: Dict,
    image_dir: Path,
    download_images: bool,
    force: bool,
    existing_images: Optional[Dict[str, Dict]] = None,
) -> Dict:
    image_sources = extract_article_image_urls(article)
    image_records = []
    for index, image in enumerate(image_sources, start=1):
        url = image["url"]
        record = {
            "source": image["source"],
            "url": url,
            "path": "",
            "relative_path": "",
            "downloaded": False,
            "skipped_existing": False,
            "error": "",
        }
        previous = (existing_images or {}).get(url)
        if previous and previous.get("path"):
            record.update({
                "path": previous.get("path", ""),
                "relative_path": previous.get("relative_path", ""),
                "downloaded": bool(previous.get("downloaded", True)),
                "skipped_existing": bool(previous.get("skipped_existing", True)),
                "error": previous.get("error", ""),
            })
        if download_images:
            try:
                record.update(_download_image(url, image_dir, index, force=force))
            except Exception as exc:
                record["error"] = str(exc)
                logger.warning("Image download failed: %s %s", url[:100], exc)
        image_records.append(record)

    publish_time = int(article.get("publish_time") or 0)
    fetched_at = int(article.get("fetched_at") or 0)

    return {
        "id": article.get("id"),
        "fakeid": article.get("fakeid", ""),
        "account_name": article.get("nickname", "") or article.get("fakeid", ""),
        "account_alias": article.get("alias", ""),
        "aid": article.get("aid", ""),
        "title": article.get("title", ""),
        "link": article.get("link", ""),
        "digest": article.get("digest", ""),
        "cover": article.get("cover", ""),
        "author": article.get("author", ""),
        "publish_time": publish_time,
        "publish_time_iso": datetime.fromtimestamp(publish_time, _get_timezone()).isoformat() if publish_time else "",
        "fetched_at": fetched_at,
        "fetched_at_iso": datetime.fromtimestamp(fetched_at, _get_timezone()).isoformat() if fetched_at else "",
        "content": article.get("content", ""),
        "plain_content": article.get("plain_content", ""),
        "source": article.get("source", ""),
        "images": image_records,
    }


def _existing_image_records_by_article(archive_file: Path) -> Dict[str, Dict[str, Dict]]:
    if not archive_file.exists():
        return {}
    try:
        payload = json.loads(archive_file.read_text(encoding="utf-8"))
    except Exception:
        return {}

    records: Dict[str, Dict[str, Dict]] = {}
    for account in payload.get("accounts", []):
        for article in account.get("articles", []):
            key = article.get("link") or str(article.get("id") or "")
            if not key:
                continue
            by_url = {}
            for image in article.get("images", []):
                url = image.get("url")
                if url:
                    by_url[url] = image
            if by_url:
                records[key] = by_url
    return records


def archive_daily_articles(
    date_str: Optional[str] = None,
    fakeid: Optional[str] = None,
    download_images: Optional[bool] = None,
    force: bool = False,
) -> Dict:
    """
    Archive one day's cached articles into JSON and local image files.

    Args:
        date_str: Local date in YYYY-MM-DD. Defaults to today.
        fakeid: Optional subscription fakeid filter.
        download_images: Defaults to DAILY_ARCHIVE_DOWNLOAD_IMAGES=true.
        force: Re-download images even if the target file already exists.
    """
    target_date = _parse_date(date_str)
    start_ts, end_ts = _day_bounds(target_date)
    if download_images is None:
        download_images = os.getenv("DAILY_ARCHIVE_DOWNLOAD_IMAGES", "true").lower() == "true"

    articles = rss_store.get_articles_between(start_ts, end_ts, fakeid=fakeid)
    archive_dir = get_archive_dir(target_date.strftime("%Y-%m-%d"))
    archive_file = get_archive_file(target_date.strftime("%Y-%m-%d"))
    images_root = archive_dir / "images"
    archive_dir.mkdir(parents=True, exist_ok=True)
    existing_images_by_article = _existing_image_records_by_article(archive_file)

    grouped: Dict[str, Dict] = {}
    total_images = 0
    downloaded_images = 0
    failed_images = 0

    for article in articles:
        account_key = article.get("fakeid", "")
        account = grouped.setdefault(account_key, {
            "fakeid": account_key,
            "nickname": article.get("nickname", ""),
            "alias": article.get("alias", ""),
            "head_img": article.get("head_img", ""),
            "article_count": 0,
            "articles": [],
        })

        article_slug = _safe_name(article.get("title", ""), f"article_{article.get('id', '')}")
        account_slug = _safe_name(article.get("nickname", "") or account_key, account_key[:12] or "account")
        image_dir = images_root / account_slug / article_slug
        existing_key = article.get("link") or str(article.get("id") or "")
        item = _serialize_article(
            article,
            image_dir,
            download_images,
            force,
            existing_images_by_article.get(existing_key),
        )

        total_images += len(item["images"])
        downloaded_images += sum(1 for img in item["images"] if img.get("downloaded"))
        failed_images += sum(1 for img in item["images"] if img.get("error"))

        account["articles"].append(item)
        account["article_count"] += 1

    accounts = sorted(grouped.values(), key=lambda x: x.get("nickname") or x.get("fakeid"))
    payload = {
        "date": target_date.strftime("%Y-%m-%d"),
        "timezone": ARCHIVE_TIMEZONE,
        "generated_at": int(time.time()),
        "generated_at_iso": datetime.now(_get_timezone()).isoformat(),
        "archive_dir": str(archive_dir),
        "image_dir": str(images_root),
        "fakeid": fakeid or "",
        "article_count": len(articles),
        "account_count": len(accounts),
        "image_count": total_images,
        "downloaded_image_count": downloaded_images,
        "failed_image_count": failed_images,
        "download_images": bool(download_images),
        "accounts": accounts,
    }

    archive_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Daily archive written: %s articles=%d images=%d downloaded=%d failed=%d",
        archive_file, len(articles), total_images, downloaded_images, failed_images,
    )
    return payload


def archive_today() -> Dict:
    return archive_daily_articles(_current_date_string())
