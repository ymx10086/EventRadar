#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 tmwgsicp
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file in the project root for full license text.
# SPDX-License-Identifier: AGPL-3.0-only
"""
EventRadar - FastAPI 主应用。
"""

from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# 导入路由
from routes import article, articles, search, admin, login, image, health, stats, rss, account, events, automation
from utils import event_store
from utils.rss_store import init_db
from utils.event_store import init_db as init_event_db
from utils.rss_poller import rss_poller
from utils.event_automation import event_automation

API_DESCRIPTION = """
EventRadar 是一个面向多平台内容的活动情报与日历系统，当前先支持微信公众号文章抓取、链接/文本/图片导入、图片理解、活动抽取、去重入库、日历展示、ICS 订阅和定时自动化。

## 快速开始

1. 访问 `/login.html` 扫码登录微信公众号后台
2. 访问 `/events.html` 打开活动日历
3. 在设置中配置公众号、时间范围、定时抓取和保留策略
4. 使用手动导入或定时任务抽取活动，并通过 `/api/events/calendar.ics` 订阅到日历客户端

## 认证说明

微信公众号文章抓取能力需要先登录。登录后凭证自动保存到 `.env` 文件，服务重启后无需重新登录（有效期约 4 天）。
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动和关闭"""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("\n" + "=" * 60)
        print("[WARNING] .env file not found")
        print("=" * 60)
        print("Please configure .env file or login via admin page")
        print("Visit: http://localhost:5000/admin.html")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("[OK] .env file loaded")
        print("=" * 60 + "\n")

    init_db()
    init_event_db()
    refresh_result = event_store.refresh_calendar_times()
    if refresh_result.get("updated_count"):
        print(f"[OK] Event calendar times refreshed: {refresh_result['updated_count']}")
    dedupe_result = event_store.cleanup_duplicate_events()
    if dedupe_result.get("deleted_count"):
        print(f"[OK] Duplicate events cleaned: {dedupe_result['deleted_count']}")
    from utils.personal_assistant import get_settings
    settings = get_settings()
    cleanup_result = event_store.delete_old_unfavorited_events(
        int(settings.get("event_retention_days") or os.getenv("EVENT_RETENTION_DAYS", "15"))
    )
    if cleanup_result.get("deleted_count"):
        print(f"[OK] Old un-favorited events cleaned: {cleanup_result['deleted_count']}")
    event_automation.configure(settings)
    await rss_poller.start()
    await event_automation.start()
    
    # 启动登录过期提醒器（自动检测凭证有效期并 webhook 通知）
    from utils.login_reminder import login_reminder
    await login_reminder.start()
    
    yield
    
    await login_reminder.stop()
    await event_automation.stop()
    await rss_poller.stop()


app = FastAPI(
    title="EventRadar",
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    license_info={
        "name": "AGPL-3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html",
    },
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（注意：articles.router 必须在 search.router 之前注册，避免路由冲突）
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(stats.router, prefix="/api", tags=["统计信息"])
app.include_router(article.router, prefix="/api", tags=["文章内容"])
app.include_router(articles.router, prefix="/api/public", tags=["文章列表"])  # 必须先注册
app.include_router(search.router, prefix="/api/public", tags=["公众号搜索"])  # 后注册
app.include_router(account.router, prefix="/api/public", tags=["公众号信息"])
app.include_router(admin.router, prefix="/api/admin", tags=["管理"])
app.include_router(login.router, prefix="/api/login", tags=["登录"])
app.include_router(image.router, prefix="/api", tags=["图片代理"])
app.include_router(rss.router, prefix="/api", tags=["RSS 订阅"])
app.include_router(events.router, prefix="/api/events", tags=["活动抽取"])
app.include_router(automation.router, prefix="/api/automation", tags=["活动自动化"])

# 静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/api/redoc", include_in_schema=False)
async def redoc_html():
    """ReDoc 文档（使用 cdnjs 加速）"""
    return HTMLResponse("""<!DOCTYPE html>
<html><head>
<title>EventRadar - ReDoc</title>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
<style>body{margin:0;padding:0;}</style>
</head><body>
<redoc spec-url='/api/openapi.json'></redoc>
<script src="https://cdnjs.cloudflare.com/ajax/libs/redoc/2.1.5/bundles/redoc.standalone.min.js"></script>
</body></html>""")

# 静态页面路由
@app.get("/", include_in_schema=False)
async def root():
    """首页 - 我的活动日历"""
    return FileResponse(static_dir / "events.html")

@app.get("/admin.html", include_in_schema=False)
async def admin_page():
    """管理页面"""
    return FileResponse(static_dir / "admin.html")

@app.get("/login.html", include_in_schema=False)
async def login_page():
    """登录页面"""
    return FileResponse(static_dir / "login.html")

@app.get("/verify.html", include_in_schema=False)
async def verify_page():
    """验证页面"""
    return FileResponse(static_dir / "verify.html")

@app.get("/rss.html", include_in_schema=False)
async def rss_page():
    """RSS 订阅管理页面"""
    return FileResponse(static_dir / "rss.html")

@app.get("/categories.html", include_in_schema=False)
async def categories_page():
    """分类管理页面"""
    return FileResponse(static_dir / "categories.html")

@app.get("/blacklist.html", include_in_schema=False)
async def blacklist_page():
    """黑名单管理页面"""
    return FileResponse(static_dir / "blacklist.html")

@app.get("/history.html", include_in_schema=False)
async def history_page():
    """历史文章获取页面"""
    return FileResponse(static_dir / "history.html")

@app.get("/events.html", include_in_schema=False)
async def events_page():
    """活动抽取页面"""
    return FileResponse(static_dir / "events.html")

if __name__ == "__main__":
    import os
    import socket
    import urllib.request
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    site_url = os.getenv("SITE_URL", "").strip().rstrip("/")
    public_url = os.getenv("PUBLIC_URL", "").strip().rstrip("/")

    def _local_lan_ip() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            return ""

    def _public_ip() -> str:
        if public_url:
            return public_url
        if site_url and "localhost" not in site_url and "127.0.0.1" not in site_url:
            return site_url
        for endpoint in ("https://api.ipify.org", "https://ifconfig.me/ip"):
            try:
                with urllib.request.urlopen(endpoint, timeout=2) as resp:
                    ip = resp.read().decode("utf-8").strip()
                    if ip:
                        if ":" in ip and not ip.startswith("["):
                            return f"http://[{ip}]:{port}"
                        return f"http://{ip}:{port}"
            except Exception:
                continue
        return ""

    lan_ip = _local_lan_ip()
    lan_url = f"http://{lan_ip}:{port}" if lan_ip else ""
    external_url = _public_ip()

    print("=" * 60)
    print("EventRadar - FastAPI Service")
    print("=" * 60)
    print(f"Admin Page: http://localhost:{port}/admin.html")
    print(f"Events Page: http://localhost:{port}/events.html")
    if lan_url:
        print(f"LAN Page:   {lan_url}/admin.html")
    if external_url:
        print(f"Public Events: {external_url}/events.html")
        print(f"Public Admin:  {external_url}/admin.html")
    elif host in ("0.0.0.0", "::"):
        print("Public URL: set PUBLIC_URL or SITE_URL in .env to show a fixed public address")
    print(f"API Docs:   http://localhost:{port}/api/docs")
    print(f"ReDoc Docs: http://localhost:{port}/api/redoc")
    print("First time? Please login via admin page")
    print("=" * 60)

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="debug" if debug else "info",
    )
