#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Persistent event store.

Stores extracted events so the UI can provide a long-lived calendar, review
workflow, and stable ICS subscription independent of one-off export files.
"""

import json
import os
import sqlite3
import time
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import re
from zoneinfo import ZoneInfo

DEFAULT_DB = Path(__file__).parent.parent / "data" / "events.db"
DB_PATH = Path(os.getenv("EVENTS_DB_PATH", str(DEFAULT_DB)))
DATA_ROOT = Path(os.getenv("EVENTRADAR_DATA_DIR", str(Path(__file__).parent.parent / "data")))


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                account TEXT NOT NULL DEFAULT '',
                source_article_title TEXT NOT NULL DEFAULT '',
                source_article_url TEXT NOT NULL DEFAULT '',
                source_publish_time TEXT NOT NULL DEFAULT '',
                start_time TEXT NOT NULL DEFAULT '',
                end_time TEXT NOT NULL DEFAULT '',
                calendar_time TEXT NOT NULL DEFAULT '',
                calendar_time_label TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                organizer TEXT NOT NULL DEFAULT '',
                signup_start_time TEXT NOT NULL DEFAULT '',
                signup_deadline TEXT NOT NULL DEFAULT '',
                signup_url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'event',
                tags TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'B',
                status TEXT NOT NULL DEFAULT 'pending',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                evidence TEXT NOT NULL DEFAULT '',
                level_reason TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                image_paths TEXT NOT NULL DEFAULT '[]',
                extraction_method TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                confirmed_at INTEGER DEFAULT NULL,
                ignored_at INTEGER DEFAULT NULL,
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_events_time ON events(start_time);
            CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
            CREATE INDEX IF NOT EXISTS idx_events_priority ON events(priority);
            CREATE INDEX IF NOT EXISTS idx_events_account ON events(account);
        """)
        cursor = conn.execute("PRAGMA table_info(events)")
        columns = {row["name"] for row in cursor.fetchall()}
        migrations = {
            "city": "ALTER TABLE events ADD COLUMN city TEXT NOT NULL DEFAULT ''",
            "calendar_time": "ALTER TABLE events ADD COLUMN calendar_time TEXT NOT NULL DEFAULT ''",
            "calendar_time_label": "ALTER TABLE events ADD COLUMN calendar_time_label TEXT NOT NULL DEFAULT ''",
            "signup_start_time": "ALTER TABLE events ADD COLUMN signup_start_time TEXT NOT NULL DEFAULT ''",
            "is_favorite": "ALTER TABLE events ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0",
            "tags": "ALTER TABLE events ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'",
            "level_reason": "ALTER TABLE events ADD COLUMN level_reason TEXT NOT NULL DEFAULT ''",
            "source_type": "ALTER TABLE events ADD COLUMN source_type TEXT NOT NULL DEFAULT ''",
            "source_name": "ALTER TABLE events ADD COLUMN source_name TEXT NOT NULL DEFAULT ''",
            "source_url": "ALTER TABLE events ADD COLUMN source_url TEXT NOT NULL DEFAULT ''",
        }
        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_calendar_time ON events(calendar_time)")
        conn.commit()
    finally:
        conn.close()


def _priority_for_event(event: Dict) -> str:
    try:
        from utils.personal_assistant import grade_event

        return grade_event(event).get("priority", "B")
    except Exception:
        pass

    confidence = float(event.get("confidence") or 0)
    category = str(event.get("category") or "").lower()
    title = str(event.get("title") or "")
    signup_deadline = str(event.get("signup_deadline") or "")

    score = confidence * 60
    if any(k in category for k in ["大赛", "competition", "contest"]):
        score += 18
    if any(k in category for k in ["课程", "讲座", "lecture", "forum", "论坛"]):
        score += 10
    if signup_deadline:
        score += 10
    if any(k in title for k in ["报名", "招募", "开放", "预告", "Now Open"]):
        score += 8

    if score >= 78:
        return "S"
    if score >= 62:
        return "A"
    if score >= 42:
        return "B"
    return "C"


def _event_date_for_dedupe(event: Dict) -> str:
    return _date_key(
        event.get("calendar_time")
        or event.get("signup_start_time")
        or event.get("signup_deadline")
        or event.get("start_time")
        or event.get("end_time")
        or ""
    )


def _event_title_key(value: str) -> str:
    text = _compact_for_match(value)
    noise = [
        "活动", "报名", "开启", "来啦", "预告", "官宣", "倒计时", "通知",
        "stop1", "北京站", "线上", "线下", "初赛", "决赛",
    ]
    for item in noise:
        text = text.replace(item, "")
    return text or _compact_for_match(value)


def _event_dedupe_scope(event: Dict) -> str:
    for field in ("source_article_url", "source_url", "signup_url", "registration_link"):
        value = str(event.get(field) or "").strip()
        if value:
            return value
    account = str(event.get("account") or event.get("source_name") or "").strip()
    title = str(event.get("source_article_title") or event.get("title") or "").strip()
    return f"{account}|{title}"


def _event_dedupe_key(event: Dict) -> str:
    scope = _event_dedupe_scope(event)
    date_key = _event_date_for_dedupe(event)
    title_key = _event_title_key(event.get("title") or event.get("source_article_title") or "")
    location_key = _compact_for_match(event.get("location") or event.get("city") or "")
    seed = "|".join([scope, date_key, title_key[:32], location_key[:24]])
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _events_are_duplicates(left: Dict, right: Dict) -> bool:
    same_scope = _event_dedupe_scope(left) == _event_dedupe_scope(right)
    if (
        same_scope
        and (
            str(left.get("extraction_method") or "").lower() == "fallback"
            or str(right.get("extraction_method") or "").lower() == "fallback"
        )
    ):
        return True
    return _events_match_same_day(left, right, require_strong_title=not same_scope)


def _events_match_same_day(left: Dict, right: Dict, require_strong_title: bool = False) -> bool:
    """Match the same real-world event even if it came from another article/source."""
    if (
        not require_strong_title
        and (
            str(left.get("extraction_method") or "").lower() == "fallback"
            or str(right.get("extraction_method") or "").lower() == "fallback"
        )
    ):
        return True
    left_title = _event_title_key(left.get("title") or left.get("source_article_title") or "")
    right_title = _event_title_key(right.get("title") or right.get("source_article_title") or "")
    similarity = _title_similarity(left_title, right_title)
    title_matches = bool(
        not left_title
        or not right_title
        or left_title in right_title
        or right_title in left_title
        or similarity >= (0.62 if require_strong_title else 0.45)
    )
    if require_strong_title and not title_matches:
        return False
    left_date = _event_date_for_dedupe(left)
    right_date = _event_date_for_dedupe(right)
    if title_matches and (not left_date or not right_date):
        return not require_strong_title
    if left_date and right_date and left_date != right_date:
        return False
    left_location = _compact_for_match(left.get("location") or left.get("city") or "")
    right_location = _compact_for_match(right.get("location") or right.get("city") or "")
    if left_location and right_location and left_location not in right_location and right_location not in left_location:
        return False
    if left_date and right_date:
        return True
    return title_matches


def _event_quality_score(event: Dict) -> float:
    score = float(event.get("confidence") or 0) * 100
    method = str(event.get("extraction_method") or "").lower()
    if method and method != "fallback":
        score += 30
    if event.get("start_time"):
        score += 12
    if event.get("calendar_time"):
        score += 12
    if event.get("location"):
        score += 8
    if event.get("signup_deadline") or event.get("signup_start_time"):
        score += 6
    if event.get("description"):
        score += min(10, len(str(event.get("description"))) / 120)
    return score


def _row_with_raw_event(row: sqlite3.Row) -> Dict:
    item = dict(row)
    try:
        raw = json.loads(item.get("raw_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}
    return {**item, **raw}


def _find_existing_same_day(conn: sqlite3.Connection, event: Dict) -> Optional[sqlite3.Row]:
    date_key = _event_date_for_dedupe(event)
    if not date_key:
        return None
    rows = conn.execute(
        """
        SELECT * FROM events
        WHERE calendar_time LIKE ?
           OR start_time LIKE ?
           OR signup_start_time LIKE ?
           OR signup_deadline LIKE ?
        ORDER BY is_favorite DESC, confirmed_at IS NOT NULL DESC, confidence DESC, updated_at DESC
        LIMIT 120
        """,
        (date_key + "%", date_key + "%", date_key + "%", date_key + "%"),
    ).fetchall()
    for row in rows:
        if _events_match_same_day(event, _row_with_raw_event(row), require_strong_title=True):
            return row
    return None


def save_events(events: List[Dict]) -> int:
    """Upsert extracted events. Manual status/priority edits are preserved."""
    init_db()
    now = int(time.time())
    saved = 0
    conn = _conn()
    try:
        for event in events:
            try:
                from utils.personal_assistant import normalize_event

                event = normalize_event(event)
            except Exception:
                event = dict(event)

            event_id = str(event.get("id") or "").strip()
            if not event_id:
                continue

            dedupe_key = _event_dedupe_key(event)
            existing = conn.execute(
                "SELECT * FROM events WHERE id=?",
                (event_id,),
            ).fetchone()
            if not existing:
                existing = conn.execute(
                    "SELECT * FROM events WHERE json_extract(raw_json, '$._dedupe_key')=? ORDER BY is_favorite DESC, confirmed_at IS NOT NULL DESC, confidence DESC, updated_at DESC LIMIT 1",
                    (dedupe_key,),
                ).fetchone()
            if not existing:
                candidates = conn.execute(
                    """
                    SELECT * FROM events
                    WHERE COALESCE(NULLIF(source_article_url, ''), NULLIF(source_url, ''), NULLIF(signup_url, '')) =
                          COALESCE(NULLIF(?, ''), NULLIF(?, ''), NULLIF(?, ''))
                    ORDER BY is_favorite DESC, confirmed_at IS NOT NULL DESC, confidence DESC, updated_at DESC
                    LIMIT 50
                    """,
                    (
                        event.get("source_article_url", ""),
                        event.get("source_url", ""),
                        event.get("signup_url", ""),
                    ),
                ).fetchall()
                for candidate in candidates:
                    if _events_are_duplicates(event, _row_with_raw_event(candidate)):
                        existing = candidate
                        break
            if not existing:
                existing = _find_existing_same_day(conn, event)
            if existing and existing["id"] != event_id:
                event_id = existing["id"]
                old_raw = _row_with_raw_event(existing)
                if (
                    existing["status"] == "confirmed"
                    or int(existing["is_favorite"] or 0)
                    or _event_quality_score(old_raw or dict(existing)) > _event_quality_score(event)
                ):
                    new_favorite = bool(event.get("is_favorite") or event.get("favorite"))
                    event = {**event, **old_raw, "id": event_id}
                    if new_favorite:
                        event["is_favorite"] = True
                        event["favorite"] = True
                        conn.execute("UPDATE events SET is_favorite=1 WHERE id=?", (event_id,))
                else:
                    event["id"] = event_id
            event["_dedupe_key"] = dedupe_key
            status = existing["status"] if existing else "pending"
            priority = existing["priority"] if existing else event.get("level") or event.get("priority") or _priority_for_event(event)
            is_favorite = max(
                int(existing["is_favorite"]) if existing else 0,
                int(bool(event.get("is_favorite") or event.get("favorite"))),
            )
            note = existing["note"] if existing else ""
            confirmed_at = existing["confirmed_at"] if existing else None
            ignored_at = existing["ignored_at"] if existing else None
            image_paths = event.get("image_paths", [])
            if existing and not image_paths:
                try:
                    image_paths = json.loads(existing["image_paths"] or "[]")
                except json.JSONDecodeError:
                    image_paths = []

            if status not in {"pending", "confirmed", "ignored"}:
                status = "pending"
            if priority not in {"S", "A", "B", "C"}:
                priority = _priority_for_event(event)

            conn.execute(
                """
                INSERT INTO events (
                    id, title, account, source_article_title, source_article_url,
                    source_publish_time, start_time, end_time, calendar_time,
                    calendar_time_label, location, city, organizer, signup_start_time,
                    signup_deadline, signup_url, description, category, tags, confidence,
                    priority, status, is_favorite, evidence, level_reason, source_type, source_name,
                    source_url, image_paths, extraction_method, raw_json, created_at,
                    updated_at, confirmed_at, ignored_at, note
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    account=excluded.account,
                    source_article_title=excluded.source_article_title,
                    source_article_url=excluded.source_article_url,
                    source_publish_time=excluded.source_publish_time,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    calendar_time=excluded.calendar_time,
                    calendar_time_label=excluded.calendar_time_label,
                    location=excluded.location,
                    city=excluded.city,
                    organizer=excluded.organizer,
                    signup_start_time=excluded.signup_start_time,
                    signup_deadline=excluded.signup_deadline,
                    signup_url=excluded.signup_url,
                    description=excluded.description,
                    category=excluded.category,
                    tags=excluded.tags,
                    confidence=excluded.confidence,
                    is_favorite=events.is_favorite,
                    evidence=excluded.evidence,
                    level_reason=excluded.level_reason,
                    source_type=excluded.source_type,
                    source_name=excluded.source_name,
                    source_url=excluded.source_url,
                    image_paths=excluded.image_paths,
                    extraction_method=excluded.extraction_method,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                (
                    event_id,
                    event.get("title", ""),
                    event.get("account", ""),
                    event.get("source_article_title", ""),
                    event.get("source_article_url", ""),
                    event.get("source_publish_time", ""),
                    event.get("start_time", ""),
                    event.get("end_time", ""),
                    event.get("calendar_time", ""),
                    event.get("calendar_time_label", ""),
                    event.get("location", ""),
                    event.get("city", ""),
                    event.get("organizer", ""),
                    event.get("signup_start_time", ""),
                    event.get("signup_deadline", ""),
                    event.get("signup_url", ""),
                    event.get("description", ""),
                    event.get("category") or (event.get("tags") or ["event"])[0],
                    json.dumps(event.get("tags", []), ensure_ascii=False),
                    float(event.get("confidence") or 0),
                    priority,
                    status,
                    is_favorite,
                    event.get("reason") or event.get("evidence", ""),
                    event.get("reason", ""),
                    event.get("source_type", ""),
                    event.get("source_name", ""),
                    event.get("source_url", ""),
                    json.dumps(image_paths, ensure_ascii=False),
                    event.get("extraction_method", ""),
                    json.dumps(event, ensure_ascii=False),
                    now,
                    now,
                    confirmed_at,
                    ignored_at,
                    note,
                ),
            )
            saved += 1
        conn.commit()
        return saved
    finally:
        conn.close()


def refresh_calendar_times(limit: int = 5000) -> Dict:
    """Recompute stored calendar placement after time parsing rules change."""
    init_db()
    conn = _conn()
    updated_ids: List[str] = []
    try:
        rows = conn.execute("SELECT * FROM events LIMIT ?", (limit,)).fetchall()
        now = int(time.time())
        for row in rows:
            event = dict(row)
            try:
                event["tags"] = json.loads(event.get("tags") or "[]")
            except (json.JSONDecodeError, TypeError):
                event["tags"] = []
            try:
                from utils.event_extractor import calendar_time_for_event

                calendar_time, calendar_label = calendar_time_for_event(event)
            except Exception:
                continue
            if calendar_time == event.get("calendar_time", "") and calendar_label == event.get("calendar_time_label", ""):
                continue
            conn.execute(
                "UPDATE events SET calendar_time=?, calendar_time_label=?, updated_at=? WHERE id=?",
                (calendar_time, calendar_label, now, event["id"]),
            )
            updated_ids.append(event["id"])
        conn.commit()
        return {"updated_count": len(updated_ids), "updated_ids": updated_ids}
    finally:
        conn.close()


def _compact_for_match(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").lower(), flags=re.UNICODE)


def _title_similarity(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", str(left or "").lower()))
    right_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", str(right or "").lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def cleanup_duplicate_events(limit: int = 5000) -> Dict:
    """Remove conservative duplicates so repeated imports leave one calendar item."""
    init_db()
    conn = _conn()
    deleted_ids: List[str] = []
    favorite_keep_ids = set()
    confirmed_keep_ids = set()
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM events LIMIT ?", (limit,)).fetchall()]
        for row in rows:
            try:
                raw = json.loads(row.get("raw_json") or "{}")
            except (json.JSONDecodeError, TypeError):
                raw = {}
            row["_raw_event"] = {**row, **raw}
            row["_dedupe_key"] = raw.get("_dedupe_key") or _event_dedupe_key(row["_raw_event"])

        fingerprint_groups: Dict[str, List[Dict]] = {}
        for row in rows:
            key = row.get("_dedupe_key")
            if key:
                fingerprint_groups.setdefault(key, []).append(row)

        def keep_key(row: Dict) -> tuple:
            return (
                1 if int(row.get("is_favorite") or 0) else 0,
                1 if row.get("status") == "confirmed" else 0,
                _event_quality_score(row.get("_raw_event") or row),
                int(row.get("updated_at") or 0),
            )

        for group in fingerprint_groups.values():
            if len(group) < 2:
                continue
            keep = max(group, key=keep_key)
            if any(int(row.get("is_favorite") or 0) for row in group):
                favorite_keep_ids.add(keep["id"])
            if any(row.get("status") == "confirmed" for row in group):
                confirmed_keep_ids.add(keep["id"])
            for row in group:
                if row["id"] != keep["id"]:
                    deleted_ids.append(row["id"])

        groups: Dict[str, List[Dict]] = {}
        for row in rows:
            source_url = str(row.get("source_article_url") or row.get("source_url") or "").strip()
            if source_url:
                groups.setdefault(source_url, []).append(row)

        for group in groups.values():
            if len(group) < 2:
                continue
            sorted_group = sorted(group, key=keep_key, reverse=True)
            for index, row in enumerate(sorted_group):
                duplicate_of = next(
                    (other for other in sorted_group[:index] if _events_are_duplicates(row.get("_raw_event") or row, other.get("_raw_event") or other)),
                    None,
                )
                if duplicate_of:
                    if int(row.get("is_favorite") or 0):
                        favorite_keep_ids.add(duplicate_of["id"])
                    if row.get("status") == "confirmed":
                        confirmed_keep_ids.add(duplicate_of["id"])
                    deleted_ids.append(row["id"])

            stronger = [
                row for row in group
                if str(row.get("extraction_method") or "").lower() != "fallback"
            ]
            if not stronger:
                continue
            for row in group:
                if str(row.get("extraction_method") or "").lower() != "fallback":
                    continue
                if int(row.get("is_favorite") or 0) or row.get("status") == "confirmed":
                    continue
                title = str(row.get("title") or "")
                source_title = str(row.get("source_article_title") or "")
                compact_title = _compact_for_match(title)
                compact_source = _compact_for_match(source_title)
                title_is_source = bool(
                    compact_title and compact_source
                    and (compact_title in compact_source or compact_source in compact_title)
                )
                similar_to_stronger = any(
                    _title_similarity(title, str(other.get("title") or "")) >= 0.35
                    for other in stronger
                )
                if title_is_source or similar_to_stronger:
                    deleted_ids.append(row["id"])

        deleted_ids = sorted(set(deleted_ids))
        for keep_id in sorted(favorite_keep_ids):
            if keep_id not in deleted_ids:
                conn.execute("UPDATE events SET is_favorite=1 WHERE id=?", (keep_id,))
        for keep_id in sorted(confirmed_keep_ids):
            if keep_id not in deleted_ids:
                conn.execute(
                    "UPDATE events SET status='confirmed', confirmed_at=COALESCE(confirmed_at, ?) WHERE id=?",
                    (int(time.time()), keep_id),
                )
        if deleted_ids:
            placeholders = ",".join(["?"] * len(deleted_ids))
            conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", deleted_ids)
        if deleted_ids or favorite_keep_ids or confirmed_keep_ids:
            conn.commit()
        return {"deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}
    finally:
        conn.close()


def _row_to_event(row: sqlite3.Row) -> Dict:
    item = dict(row)
    try:
        item["image_paths"] = json.loads(item.get("image_paths") or "[]")
    except json.JSONDecodeError:
        item["image_paths"] = []
    try:
        item["tags"] = json.loads(item.get("tags") or "[]")
    except (json.JSONDecodeError, TypeError):
        item["tags"] = []
    if item.get("level_reason"):
        item["reason"] = item["level_reason"]
    item["level"] = item.get("priority") or "B"
    if item.get("source_name"):
        item["account"] = item.get("account") or item["source_name"]
    item["is_favorite"] = bool(item.get("is_favorite"))
    item["favorite"] = item["is_favorite"]
    try:
        from utils.personal_assistant import normalize_event

        item = normalize_event(item)
    except Exception:
        item["level"] = item.get("priority", "B")
        item["registration_deadline"] = item.get("signup_deadline", "")
        item["registration_link"] = item.get("signup_url", "")
        item["source_type"] = "wechat" if item.get("source_article_url") else "manual"
        item["source_name"] = item.get("account", "")
        item["source_url"] = item.get("source_article_url", "")
        item["tags"] = [item.get("category", "event")]
        item["reason"] = item.get("note") or item.get("evidence", "")
    return item


def dedupe_event_list(events: List[Dict]) -> List[Dict]:
    kept: List[Dict] = []
    for event in events:
        duplicate_index = next(
            (idx for idx, old in enumerate(kept) if _events_are_duplicates(event, old)),
            None,
        )
        if duplicate_index is None:
            kept.append(event)
        elif _event_quality_score(event) > _event_quality_score(kept[duplicate_index]):
            kept[duplicate_index] = event
    return kept


def list_events(start: Optional[str] = None, end: Optional[str] = None,
                status: Optional[str] = None, priority: Optional[str] = None,
                account: Optional[str] = None, include_ignored: bool = False,
                limit: int = 500, category: Optional[str] = None,
                q: Optional[str] = None, tag: Optional[str] = None,
                favorite: Optional[bool] = None) -> List[Dict]:
    init_db()
    where = []
    params = []
    if status:
        where.append("status = ?")
        params.append(status)
    elif not include_ignored:
        where.append("status != 'ignored'")
    if priority:
        where.append("priority = ?")
        params.append(priority)
    if account:
        where.append("account = ?")
        params.append(account)
    if category:
        where.append("category = ?")
        params.append(category)
    if favorite is not None:
        where.append("is_favorite = ?")
        params.append(1 if favorite else 0)

    needs_python_filter = bool(start or end or q or tag)
    query_limit = max(limit, 10000) if needs_python_filter else limit

    sql = "SELECT * FROM events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(NULLIF(calendar_time, ''), start_time) ASC, priority ASC, title ASC LIMIT ?"
    params.append(query_limit)

    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        events = [_row_to_event(row) for row in rows]
        if start or end:
            events = [
                event for event in events
                if _in_date_range(event.get("calendar_time") or event.get("start_time", ""), start, end)
            ]
        if q:
            keyword = q.strip().lower()
            events = [
                event for event in events
                if _event_matches_keyword(event, keyword)
            ]
        if tag:
            tag_lower = tag.strip().lower()
            events = [
                event for event in events
                if tag_lower in [str(item).lower() for item in event.get("tags", [])]
            ]
        events = dedupe_event_list(events)
        return events[:limit]
    finally:
        conn.close()


def _event_matches_keyword(event: Dict, keyword: str) -> bool:
    if not keyword:
        return True
    fields = [
        "title", "account", "source_article_title", "start_time", "end_time",
        "calendar_time", "calendar_time_label", "location", "city", "organizer",
        "signup_start_time", "signup_deadline", "signup_url",
        "registration_deadline", "registration_link", "description",
        "category", "source_type", "source_name", "source_url",
        "evidence", "note", "reason",
    ]
    text = " ".join(str(event.get(field) or "") for field in fields)
    text += " " + " ".join(str(item) for item in event.get("tags", []))
    text = text.lower()
    return keyword in text


def summarize_events(events: List[Dict]) -> Dict:
    summary = {
        "status_counts": {},
        "priority_counts": {},
        "category_counts": {},
        "tag_counts": {},
        "accounts": [],
        "categories": [],
        "tags": [],
        "favorite_count": 0,
    }
    accounts = set()
    categories = set()
    tags = set()
    for event in events:
        status = event.get("status") or "pending"
        priority = event.get("level") or event.get("priority") or "B"
        category = event.get("category") or "event"
        account = event.get("source_name") or event.get("account") or ""

        summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1
        summary["priority_counts"][priority] = summary["priority_counts"].get(priority, 0) + 1
        summary["category_counts"][category] = summary["category_counts"].get(category, 0) + 1
        if account:
            accounts.add(account)
        if event.get("is_favorite") or event.get("favorite"):
            summary["favorite_count"] += 1
        if category:
            categories.add(category)
        for tag in event.get("tags", []):
            if tag:
                tag = str(tag)
                tags.add(tag)
                summary["tag_counts"][tag] = summary["tag_counts"].get(tag, 0) + 1

    summary["accounts"] = sorted(accounts)
    summary["categories"] = sorted(categories)
    summary["tags"] = sorted(tags)
    return summary


def upcoming_events(days: int = 14, status: str = "confirmed", limit: int = 50) -> List[Dict]:
    tz_name = os.getenv("DAILY_ARCHIVE_TIMEZONE", "Asia/Shanghai")
    today = datetime.now(ZoneInfo(tz_name)).date()
    end = today + timedelta(days=max(0, days))
    return list_events(
        start=today.isoformat(),
        end=end.isoformat(),
        status=status,
        include_ignored=False,
        limit=limit,
    )


def _date_key(value: str) -> str:
    def valid_date(year: int, month: int, day: int) -> str:
        try:
            datetime(year, month, day)
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            return ""

    value = str(value or "")
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        return valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})(?:日)?", value)
    if match:
        return valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", value)
    if match:
        return valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"(\d{1,2})月\s*(\d{1,2})(?:日)?", value)
    if match:
        return valid_date(datetime.now(ZoneInfo(os.getenv('DAILY_ARCHIVE_TIMEZONE', 'Asia/Shanghai'))).year, int(match.group(1)), int(match.group(2)))
    match = re.search(r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?!\d)", value)
    if match:
        return valid_date(datetime.now(ZoneInfo(os.getenv('DAILY_ARCHIVE_TIMEZONE', 'Asia/Shanghai'))).year, int(match.group(1)), int(match.group(2)))
    return ""


def _in_date_range(value: str, start: Optional[str], end: Optional[str]) -> bool:
    key = _date_key(value)
    if not key:
        return False
    if start and key < start[:10]:
        return False
    if end and key > end[:10]:
        return False
    return True


def update_event(event_id: str, updates: Dict) -> Optional[Dict]:
    init_db()
    allowed = {
        "title", "start_time", "end_time", "calendar_time", "calendar_time_label",
        "location", "city", "organizer", "signup_start_time",
        "signup_deadline", "signup_url", "description", "category",
        "tags", "priority", "status", "is_favorite", "note", "level_reason",
        "source_type", "source_name", "source_url",
    }
    if "favorite" in updates and "is_favorite" not in updates:
        updates["is_favorite"] = updates["favorite"]
    if "level" in updates and "priority" not in updates:
        updates["priority"] = updates["level"]
    if "registration_deadline" in updates and "signup_deadline" not in updates:
        updates["signup_deadline"] = updates["registration_deadline"]
    if "registration_link" in updates and "signup_url" not in updates:
        updates["signup_url"] = updates["registration_link"]
    if "calendar_time" not in updates and {
        "start_time", "end_time", "signup_start_time", "signup_deadline", "registration_deadline"
    }.intersection(updates):
        existing = get_event(event_id) or {}
        candidate = {**existing, **updates}
        try:
            from utils.event_extractor import calendar_time_for_event

            calendar_time, calendar_label = calendar_time_for_event(candidate)
            updates["calendar_time"] = calendar_time
            updates["calendar_time_label"] = calendar_label
        except Exception:
            pass
    if "reason" in updates and "note" not in updates:
        updates["note"] = updates["reason"]
    if "reason" in updates and "level_reason" not in updates:
        updates["level_reason"] = updates["reason"]
    values = {k: v for k, v in updates.items() if k in allowed}
    if not values:
        return get_event(event_id)
    if isinstance(values.get("tags"), list):
        values["tags"] = json.dumps(values["tags"], ensure_ascii=False)
    if "is_favorite" in values:
        values["is_favorite"] = int(bool(values["is_favorite"]))

    now = int(time.time())
    if values.get("status") == "confirmed":
        values["confirmed_at"] = now
        values["ignored_at"] = None
    elif values.get("status") == "ignored":
        values["ignored_at"] = now
    elif values.get("status") == "pending":
        values["confirmed_at"] = None
        values["ignored_at"] = None
    allowed.update({"confirmed_at", "ignored_at"})
    values = {k: v for k, v in values.items() if k in allowed}
    values["updated_at"] = now

    assignments = ", ".join([f"{k}=?" for k in values])
    params = list(values.values()) + [event_id]
    conn = _conn()
    try:
        conn.execute(f"UPDATE events SET {assignments} WHERE id=?", params)
        conn.commit()
    finally:
        conn.close()
    return get_event(event_id)


def get_event(event_id: str) -> Optional[Dict]:
    init_db()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return _row_to_event(row) if row else None
    finally:
        conn.close()


def delete_event(event_id: str, delete_files: bool = True) -> Dict:
    """Permanently delete one event and optionally remove orphaned image files."""
    init_db()
    conn = _conn()
    candidate_files: List[str] = []
    referenced_files = set()
    try:
        target = conn.execute(
            "SELECT id, image_paths FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
        if not target:
            return {
                "deleted": False,
                "deleted_count": 0,
                "deleted_id": event_id,
                "deleted_file_count": 0,
                "deleted_files": [],
            }
        if delete_files:
            candidate_files = _json_list(target["image_paths"])
            rows = conn.execute(
                "SELECT id, image_paths FROM events WHERE id<>?",
                (event_id,),
            ).fetchall()
            for row in rows:
                for raw_path in _json_list(row["image_paths"]):
                    safe_path = _safe_local_file_path(raw_path)
                    if safe_path:
                        referenced_files.add(str(safe_path))
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
    finally:
        conn.close()
    deleted_files = _cleanup_unreferenced_files(candidate_files, referenced_files) if delete_files else []
    return {
        "deleted": True,
        "deleted_count": 1,
        "deleted_id": event_id,
        "deleted_file_count": len(deleted_files),
        "deleted_files": deleted_files,
    }


def delete_events(event_ids: List[str], delete_files: bool = True) -> Dict:
    """Permanently delete multiple events and clean orphaned image files once."""
    init_db()
    ids = []
    seen = set()
    for raw_id in event_ids or []:
        event_id = str(raw_id or "").strip()
        if event_id and event_id not in seen:
            ids.append(event_id)
            seen.add(event_id)
    if not ids:
        return {
            "deleted": False,
            "deleted_count": 0,
            "deleted_ids": [],
            "missing_ids": [],
            "deleted_file_count": 0,
            "deleted_files": [],
        }

    placeholders = ",".join(["?"] * len(ids))
    conn = _conn()
    candidate_files: List[str] = []
    referenced_files = set()
    deleted_ids: List[str] = []
    try:
        rows = conn.execute(
            f"SELECT id, image_paths FROM events WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        deleted_ids = [row["id"] for row in rows]
        if delete_files and deleted_ids:
            delete_set = set(deleted_ids)
            for row in rows:
                candidate_files.extend(_json_list(row["image_paths"]))
            deleted_placeholders = ",".join(["?"] * len(deleted_ids))
            remaining = conn.execute(
                f"SELECT id, image_paths FROM events WHERE id NOT IN ({deleted_placeholders})",
                deleted_ids,
            ).fetchall()
            for row in remaining:
                if row["id"] in delete_set:
                    continue
                for raw_path in _json_list(row["image_paths"]):
                    safe_path = _safe_local_file_path(raw_path)
                    if safe_path:
                        referenced_files.add(str(safe_path))
        if deleted_ids:
            deleted_placeholders = ",".join(["?"] * len(deleted_ids))
            conn.execute(f"DELETE FROM events WHERE id IN ({deleted_placeholders})", deleted_ids)
            conn.commit()
    finally:
        conn.close()

    deleted_files = _cleanup_unreferenced_files(candidate_files, referenced_files) if delete_files else []
    missing_ids = [event_id for event_id in ids if event_id not in set(deleted_ids)]
    return {
        "deleted": bool(deleted_ids),
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "missing_ids": missing_ids,
        "deleted_file_count": len(deleted_files),
        "deleted_files": deleted_files,
    }


def status_counts() -> Dict:
    init_db()
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM events GROUP BY status"
        ).fetchall()
        return {row["status"]: row["count"] for row in rows}
    finally:
        conn.close()


def _json_list(value: str) -> List[str]:
    try:
        items = json.loads(value or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if str(item or "").strip()]


def _safe_local_file_path(value: str) -> Optional[Path]:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    roots = {
        DATA_ROOT.resolve(),
        DB_PATH.parent.resolve(),
    }
    if not any(path == root or root in path.parents for root in roots):
        return None
    return path


def _cleanup_unreferenced_files(paths: List[str], referenced: set) -> List[str]:
    deleted = []
    seen = set()
    for raw_path in paths:
        path = _safe_local_file_path(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        if str(path) in referenced or not path.exists() or not path.is_file():
            continue
        try:
            path.unlink()
            deleted.append(str(path))
            parent = path.parent
            for _ in range(4):
                if parent == DATA_ROOT.resolve() or parent == DB_PATH.parent.resolve():
                    break
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        except OSError:
            continue
    return deleted


def delete_old_unfavorited_events(retention_days: int = 15) -> Dict:
    """Delete un-favorited events before the retention cutoff date."""
    init_db()
    tz_name = os.getenv("DAILY_ARCHIVE_TIMEZONE", "Asia/Shanghai")
    today = datetime.now(ZoneInfo(tz_name)).date()
    cutoff = today - timedelta(days=max(0, int(retention_days)))
    events = list_events(
        start=None,
        end=(cutoff - timedelta(days=1)).isoformat(),
        include_ignored=True,
        limit=10000,
    )
    deletable = [
        event for event in events
        if not (event.get("is_favorite") or event.get("favorite"))
    ]
    ids = [event["id"] for event in deletable if event.get("id")]
    if not ids:
        return {
            "deleted_count": 0,
            "cutoff_date": cutoff.isoformat(),
            "deleted_ids": [],
            "deleted_file_count": 0,
            "deleted_files": [],
        }

    conn = _conn()
    candidate_files = []
    referenced_files = set()
    try:
        rows = conn.execute("SELECT id, image_paths FROM events").fetchall()
        deleting = set(ids)
        for row in rows:
            paths = _json_list(row["image_paths"])
            if row["id"] in deleting:
                candidate_files.extend(paths)
            else:
                for raw_path in paths:
                    safe_path = _safe_local_file_path(raw_path)
                    if safe_path:
                        referenced_files.add(str(safe_path))
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", ids)
        conn.commit()
    finally:
        conn.close()
    deleted_files = _cleanup_unreferenced_files(candidate_files, referenced_files)
    return {
        "deleted_count": len(ids),
        "cutoff_date": cutoff.isoformat(),
        "deleted_ids": ids,
        "deleted_file_count": len(deleted_files),
        "deleted_files": deleted_files,
    }
