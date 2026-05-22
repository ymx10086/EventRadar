#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wechat fetch safety controls.

Centralizes throttling, proxy fallback policy, and verification cooldown state so
manual fetches, RSS full-content fetches, and automation share one risk budget.
"""

import asyncio
import logging
import os
import random
import time
from dataclasses import asdict, dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FetchSafetyPausedError(RuntimeError):
    """Raised when article fetching is paused by the safety controller."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _clamp_int(value, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_float(value, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


@dataclass
class FetchSafetyConfig:
    article_concurrency: int = 1
    article_delay_min: float = 8.0
    article_delay_max: float = 18.0
    account_delay: float = 20.0
    max_articles_per_account: int = 10
    verification_pause_minutes: int = 60
    verification_stop_threshold: int = 1
    proxy_required: bool = False

    def public_dict(self) -> Dict:
        payload = asdict(self)
        payload["article_delay_min"] = round(float(payload["article_delay_min"]), 2)
        payload["article_delay_max"] = round(float(payload["article_delay_max"]), 2)
        payload["account_delay"] = round(float(payload["account_delay"]), 2)
        return payload


def load_fetch_safety_config(settings: Optional[Dict] = None) -> FetchSafetyConfig:
    if settings is None:
        try:
            from utils.personal_assistant import SETTINGS_FILE, get_settings

            settings = get_settings()
            if not SETTINGS_FILE.exists():
                settings = {}
        except Exception:
            settings = {}

    def _setting_or_env(key: str, env_name: str, env_default):
        if isinstance(settings, dict) and key in settings:
            return settings.get(key)
        if isinstance(env_default, bool):
            return _env_bool(env_name, env_default)
        if isinstance(env_default, int):
            return _env_int(env_name, env_default)
        if isinstance(env_default, float):
            return _env_float(env_name, env_default)
        return os.getenv(env_name, str(env_default))

    concurrency = _clamp_int(
        _setting_or_env("wechat_fetch_concurrency", "WECHAT_FETCH_CONCURRENCY", 1),
        1,
        5,
        1,
    )
    delay_min = _clamp_float(
        _setting_or_env("wechat_fetch_delay_min", "WECHAT_FETCH_DELAY_MIN", 8.0),
        0,
        300,
        8,
    )
    delay_max = _clamp_float(
        _setting_or_env("wechat_fetch_delay_max", "WECHAT_FETCH_DELAY_MAX", 18.0),
        0,
        300,
        18,
    )
    if delay_max < delay_min:
        delay_max = delay_min

    return FetchSafetyConfig(
        article_concurrency=concurrency,
        article_delay_min=delay_min,
        article_delay_max=delay_max,
        account_delay=_clamp_float(
            _setting_or_env("wechat_account_delay", "WECHAT_ACCOUNT_DELAY", 20.0),
            0,
            600,
            20,
        ),
        max_articles_per_account=_clamp_int(
            _setting_or_env("wechat_max_articles_per_account", "WECHAT_MAX_ARTICLES_PER_ACCOUNT", 10),
            1,
            100,
            10,
        ),
        verification_pause_minutes=_clamp_int(
            _setting_or_env("wechat_verification_pause_minutes", "WECHAT_VERIFICATION_PAUSE_MINUTES", 60),
            0,
            720,
            60,
        ),
        verification_stop_threshold=_clamp_int(
            _setting_or_env("wechat_verification_stop_threshold", "WECHAT_VERIFICATION_STOP_THRESHOLD", 1),
            1,
            20,
            1,
        ),
        proxy_required=bool(_setting_or_env("wechat_proxy_required", "WECHAT_PROXY_REQUIRED", False)),
    )


def is_wechat_verification_page(html: str) -> bool:
    if not html:
        return False
    lower = html.lower()
    return (
        "verifycode" in lower
        or "请输入图片中的字符" in html
        or "环境异常" in html
        or all(marker in html for marker in ["完成验证后即可继续访问", "去验证"])
    )


class FetchSafetyController:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_article_fetch_at = 0.0
        self._cooldown_until = 0.0
        self._consecutive_verifications = 0
        self._last_verification_at = 0.0
        self._last_verification_reason = ""

    def is_paused(self) -> bool:
        return self._cooldown_until > time.time()

    def cooldown_remaining_seconds(self) -> int:
        return max(0, int(self._cooldown_until - time.time()))

    async def wait_article_slot(self, context: str = ""):
        config = load_fetch_safety_config()
        async with self._lock:
            if self.is_paused():
                raise FetchSafetyPausedError(self.pause_message())
            now = time.time()
            gap = random.uniform(config.article_delay_min, config.article_delay_max)
            wait_seconds = max(0.0, self._last_article_fetch_at + gap - now)
            if wait_seconds > 0:
                logger.info(
                    "[FetchSafety] waiting %.1fs before fetching article%s",
                    wait_seconds,
                    f" ({context[:60]})" if context else "",
                )
                await asyncio.sleep(wait_seconds)
            if self.is_paused():
                raise FetchSafetyPausedError(self.pause_message())
            self._last_article_fetch_at = time.time()

    def record_success(self):
        self._consecutive_verifications = 0

    def record_verification(self, reason: str = "wechat_verification") -> Dict:
        config = load_fetch_safety_config()
        now = time.time()
        self._consecutive_verifications += 1
        self._last_verification_at = now
        self._last_verification_reason = reason
        if (
            config.verification_pause_minutes > 0
            and self._consecutive_verifications >= config.verification_stop_threshold
        ):
            self._cooldown_until = max(
                self._cooldown_until,
                now + config.verification_pause_minutes * 60,
            )
            logger.warning(
                "[FetchSafety] verification threshold reached (%d), pausing fetches for %d minutes",
                self._consecutive_verifications,
                config.verification_pause_minutes,
            )
        return self.status()

    def clear_pause(self):
        self._cooldown_until = 0.0
        self._consecutive_verifications = 0

    def pause_message(self) -> str:
        remaining = self.cooldown_remaining_seconds()
        minutes = max(1, (remaining + 59) // 60)
        return f"微信安全验证触发，已进入防风控冷却，约 {minutes} 分钟后再抓取"

    def status(self) -> Dict:
        config = load_fetch_safety_config()
        try:
            from utils.proxy_pool import proxy_pool

            proxy_status = proxy_pool.get_status()
        except Exception:
            proxy_status = {}
        return {
            "paused": self.is_paused(),
            "cooldown_remaining_seconds": self.cooldown_remaining_seconds(),
            "consecutive_verifications": self._consecutive_verifications,
            "last_verification_at": int(self._last_verification_at or 0),
            "last_verification_reason": self._last_verification_reason,
            "config": config.public_dict(),
            "proxy_pool": proxy_status,
        }


fetch_safety = FetchSafetyController()
