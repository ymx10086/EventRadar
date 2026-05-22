#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat account discovery helpers.

The discovery layer reuses the logged-in WeChat public platform search API,
scores candidates against user keywords, and records the latest recommendation
snapshot for the frontend.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from utils import rss_store
from utils.auth_manager import auth_manager

DEFAULT_DISCOVERY_DIR = Path(__file__).parent.parent / "data" / "discovery"
DISCOVERY_DIR = Path(os.getenv("ACCOUNT_DISCOVERY_DIR", str(DEFAULT_DISCOVERY_DIR)))
RECOMMENDATIONS_FILE = DISCOVERY_DIR / "recommendations.json"

DEFAULT_KEYWORDS = [
    "北大 创新创业",
    "北京大学 创新创业",
    "北大 就业创业",
    "高校 创新创业 大赛",
    "AI 创业 活动",
    "大学生 创业 大赛",
]

HIGH_VALUE_TERMS = [
    "北大", "北京大学", "清华", "高校", "大学", "学院",
    "创新", "创业", "就业", "科创", "竞赛", "大赛",
    "讲座", "论坛", "路演", "孵化", "投资", "AI",
]

LOW_VALUE_TERMS = ["广告", "代运营", "营销号", "贷款", "博彩", "优惠券"]


def parse_keywords(value: Optional[str] = None) -> List[str]:
    if value is None:
        value = os.getenv("ACCOUNT_DISCOVERY_KEYWORDS", "")
    if not value.strip():
        return DEFAULT_KEYWORDS[:]
    return [item.strip() for item in re.split(r"[,，\n]", value) if item.strip()]


def score_candidate(account: Dict, keyword: str, subscribed_fakeids: Optional[set] = None) -> Dict:
    subscribed_fakeids = subscribed_fakeids or set()
    nickname = str(account.get("nickname") or "")
    alias = str(account.get("alias") or "")
    fakeid = str(account.get("fakeid") or "")
    haystack = f"{nickname} {alias}".lower()
    keyword_parts = [p for p in re.split(r"\s+", keyword.strip()) if p]

    score = 20
    reasons = []
    if fakeid in subscribed_fakeids:
        score -= 35
        reasons.append("已订阅")

    for part in keyword_parts:
        part_lower = part.lower()
        if part and part in nickname:
            score += 28
            reasons.append(f"名称匹配：{part}")
        elif part_lower and part_lower in alias.lower():
            score += 14
            reasons.append(f"微信号匹配：{part}")

    for term in HIGH_VALUE_TERMS:
        if term.lower() in haystack:
            score += 8
            reasons.append(term)

    for term in LOW_VALUE_TERMS:
        if term in nickname or term in alias:
            score -= 30
            reasons.append(f"降权：{term}")

    if account.get("service_type") == 1:
        score += 4
    if nickname and len(nickname) <= 14:
        score += 3

    return {
        "score": max(0, min(100, score)),
        "reasons": list(dict.fromkeys(reasons))[:8],
    }


async def _search_wechat_accounts(keyword: str, count: int = 5) -> List[Dict]:
    credentials = auth_manager.get_credentials()
    if not credentials:
        raise RuntimeError("服务器未登录，请先扫码登录")

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(
            "https://mp.weixin.qq.com/cgi-bin/searchbiz",
            params={
                "action": "search_biz",
                "token": credentials["token"],
                "lang": "zh_CN",
                "f": "json",
                "ajax": 1,
                "random": time.time(),
                "query": keyword,
                "begin": 0,
                "count": count,
            },
            headers={
                "Cookie": credentials["cookie"],
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
    result = response.json()
    base_resp = result.get("base_resp", {})
    if base_resp.get("ret") != 0:
        raise RuntimeError(f"{keyword} 搜索失败: {base_resp.get('err_msg', 'unknown')}")
    return result.get("list", [])


async def discover_accounts(
    keywords: Optional[List[str]] = None,
    limit_per_keyword: int = 5,
    max_results: int = 30,
    min_score: int = 0,
) -> Dict:
    keywords = [k.strip() for k in (keywords or parse_keywords()) if k.strip()]
    subscribed = {s["fakeid"] for s in rss_store.list_subscriptions()}
    blacklisted = set(rss_store.get_active_blacklist_fakeids())
    candidates: Dict[str, Dict] = {}
    errors = []

    for keyword in keywords:
        try:
            accounts = await _search_wechat_accounts(keyword, limit_per_keyword)
        except Exception as exc:
            errors.append({"keyword": keyword, "error": str(exc)})
            continue

        for account in accounts:
            fakeid = account.get("fakeid", "")
            if not fakeid or fakeid in blacklisted:
                continue
            scored = score_candidate(account, keyword, subscribed)
            if scored["score"] < min_score:
                continue
            item = candidates.get(fakeid, {
                "fakeid": fakeid,
                "nickname": account.get("nickname", ""),
                "alias": account.get("alias", ""),
                "head_img": account.get("round_head_img", ""),
                "service_type": account.get("service_type", 0),
                "score": 0,
                "reasons": [],
                "source_keywords": [],
                "subscribed": fakeid in subscribed,
            })
            if scored["score"] > item["score"]:
                item["score"] = scored["score"]
            item["reasons"] = list(dict.fromkeys(item["reasons"] + scored["reasons"]))[:10]
            item["source_keywords"] = list(dict.fromkeys(item["source_keywords"] + [keyword]))
            candidates[fakeid] = item

    results = sorted(
        candidates.values(),
        key=lambda item: (item["subscribed"], -item["score"], item["nickname"]),
    )[:max_results]
    payload = {
        "generated_at": int(time.time()),
        "keywords": keywords,
        "candidate_count": len(results),
        "error_count": len(errors),
        "errors": errors,
        "candidates": results,
    }
    save_recommendations(payload)
    return payload


def save_recommendations(payload: Dict):
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    RECOMMENDATIONS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_recommendations() -> Dict:
    if not RECOMMENDATIONS_FILE.exists():
        return {
            "generated_at": 0,
            "keywords": parse_keywords(),
            "candidate_count": 0,
            "error_count": 0,
            "errors": [],
            "candidates": [],
        }
    return json.loads(RECOMMENDATIONS_FILE.read_text(encoding="utf-8"))


def subscribe_top_candidates(payload: Dict, top_n: int = 0) -> List[Dict]:
    """Subscribe the top N currently-unsubscribed candidates from a payload."""
    subscribed = []
    if top_n <= 0:
        return subscribed
    for item in payload.get("candidates", []):
        if item.get("subscribed"):
            continue
        if len(subscribed) >= top_n:
            break
        added = rss_store.add_subscription(
            fakeid=item["fakeid"],
            nickname=item.get("nickname", ""),
            alias=item.get("alias", ""),
            head_img=item.get("head_img", ""),
        )
        if added:
            item["subscribed"] = True
            subscribed.append(item)
    payload["subscribed_count"] = len(subscribed)
    payload["subscribed"] = subscribed
    save_recommendations(payload)
    return subscribed
