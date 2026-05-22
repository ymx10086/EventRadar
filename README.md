<p align="center">
  <img src="imgs/EventRadar.png" alt="EventRadar" width="680">
</p>

<p align="center">
  <strong>Multi-source event radar that discovers events from WeChat posts, links, text, and images, enriches them with vision understanding, deduplicates them, and turns them into a subscribable calendar.</strong>
</p>

<p align="center">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-2563eb.svg?style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/runtime-FastAPI-0f766e.svg?style=flat-square">
  <img alt="SQLite" src="https://img.shields.io/badge/storage-SQLite-475569.svg?style=flat-square">
  <img alt="MiniMax Vision" src="https://img.shields.io/badge/AI-MiniMax%20Vision-0891b2.svg?style=flat-square">
  <img alt="ICS Calendar" src="https://img.shields.io/badge/export-ICS%20Calendar-f97316.svg?style=flat-square">
  <a href="LICENSE"><img alt="License AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-16a34a.svg?style=flat-square"></a>
</p>

<p align="center">
  WeChat Fetching · Daily Archives · Vision Understanding · Event Extraction · Dedupe · ICS Calendar · Automation
</p>

<p align="center">
  <a href="README.zh-CN.md">中文</a> ·
  <a href="#why-eventradar">Why</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#what-you-get-today">Features</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#api-reference">API</a> ·
  <a href="#configuration">Configuration</a>
</p>

## Why EventRadar

EventRadar is a local-first event intelligence tool. It currently focuses on WeChat article fetching, RSS subscriptions, and image archiving, while leaving room for future sources such as Xiaohongshu, web links, group-chat text, and event posters. It adds MiniMax-powered vision understanding, structured event extraction, deduplication, review workflows, automation, and ICS calendar subscriptions for lectures, competitions, registrations, roadshows, open days, summits, hackathons, and more.

This project is built on top of the open-source **WeChat Download API** project. The original project provides the WeChat login, article fetching, RSS, anti-risk controls, and image proxy foundation; EventRadar extends it into a calendar-centered event intelligence system.

| Pain Point | How EventRadar Helps |
| --- | --- |
| Event information is scattered across posts, posters, links, and text. | Archive multi-source content and extract structured event records. |
| Image-only posters are hard to search, copy, and organize. | Use MiniMax vision understanding to read event names, times, locations, signup methods, and organizers. |
| Repeated imports can quickly clutter a calendar. | Dedupe at storage, listing, and ICS layers while preserving favorite and confirmed states. |
| Event start, signup open, and deadline times are often mixed together. | Place events by the earliest actionable time whenever possible. |
| Manual calendar maintenance is expensive. | Support scheduled polling, archiving, extraction, cleanup, and ICS subscriptions. |

Under the hood, EventRadar combines:

- **FastAPI runtime**: static pages, API routes, startup tasks, and health checks.
- **WeChat and RSS foundation**: login, account search, subscription, polling, article parsing, and image proxying.
- **Daily archive pipeline**: persist articles and images by date.
- **Event extraction pipeline**: MiniMax plus fallback rules turn article text and image understanding results into events.
- **SQLite event store**: dedupe, status, priority, favorite, cleanup, CSV, and ICS.
- **Browser calendar UI**: review, filtering, editing, manual entry, settings, and automation progress.

## What You Get Today

- **WeChat fetching and RSS foundation**: log in by QR code, search and subscribe to accounts, and poll article lists and full content.
- **Daily archive**: generate `data/daily_archives/YYYY-MM-DD/articles.json` and download cover/body images.
- **Vision understanding**: image-only WeChat posts can be interpreted by MiniMax Token Plan vision to recover event details.
- **Event extraction**: combine article text and image understanding results, then extract structured events with LLM and fallback rules.
- **Calendar-first timing**: when signup open/deadline comes before the event start, the calendar can prioritize the earlier actionable date.
- **Re-import dedupe**: repeated imports for the same day, account, or article keep one event record and preserve review state.
- **Event store management**: manage `pending` / `confirmed` / `ignored` states, `S/A/B/C` priority, favorites, and cleanup rules.
- **Calendar UI and day details**: `events.html` supports filters, month/week/list views, day modals, editing, and favorites.
- **ICS subscription**: subscribe to `/api/events/calendar.ics` from Apple Calendar, Google Calendar, Outlook, and more.
- **Scheduled automation**: run scheduled polling, archiving, extraction, dedupe, saving, and progress tracking.
- **Public access**: expose the local service with `cloudflared` and a temporary `trycloudflare.com` URL when needed.

## Architecture

```text
.
├── app.py                         # FastAPI entrypoint; starts RSS, automation, and login reminders
├── routes/
│   ├── rss.py                     # RSS subscriptions, polling, and daily archive APIs
│   ├── events.py                  # Event extraction, event store, ICS, cleanup, account-range runs
│   ├── automation.py              # Automation APIs
│   ├── login.py / admin.py        # WeChat QR login and admin APIs
│   └── ...
├── utils/
│   ├── rss_poller.py              # WeChat account polling
│   ├── daily_archive.py           # Daily article and image archives
│   ├── event_extractor.py         # Vision understanding, event extraction, ICS export
│   ├── event_store.py             # Event store, dedupe, favorites, cleanup
│   ├── event_automation.py        # Scheduled pipeline and progress
│   └── ...
├── static/
│   ├── admin.html                 # Admin panel
│   └── events.html                # Main EventRadar calendar UI
├── data/
│   ├── rss.db                     # Account subscriptions and article cache
│   ├── events.db                  # Event store
│   ├── daily_archives/            # Daily article archives and images
│   └── events/                    # Daily event exports
├── env.example                    # Environment template
├── start.sh                       # Local/server startup script, optional Cloudflare Tunnel
└── docker-compose.yml
```

## Quick Start

The recommended flow is to initialize the local environment, log in to WeChat, set up RSS subscriptions, archive articles, and then run event extraction.

### 1. Create Environment

```bash
cd /path/to/eventradar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

Edit `.env` and verify at least these settings:

```env
PORT=5001
HOST=0.0.0.0
DAILY_ARCHIVE_TIMEZONE=Asia/Shanghai
DAILY_ARCHIVE_DOWNLOAD_IMAGES=true

MINIMAX_API_KEY=your MiniMax Token Plan key
MINIMAX_API_STYLE=anthropic
MINIMAX_BASE_URL=https://api.minimax.io/anthropic
MINIMAX_API_HOST=https://api.minimaxi.com
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_VISION_ENABLED=true

EVENT_AUTOMATION_ENABLED=false
EVENT_AUTOMATION_LOOKBACK_DAYS=0
EVENT_AUTOMATION_USE_LLM=true
EVENT_AUTOMATION_USE_VISION=true
EVENT_RETENTION_DAYS=15
```

Notes:

- `MINIMAX_MODEL` is used for text-based structured extraction.
- Vision understanding uses the Token Plan `/v1/coding_plan/vlm` endpoint and prefers `MINIMAX_API_HOST`, with automatic fallback between `api.minimaxi.com` and `api.minimax.io`.
- Without a MiniMax key, fallback rules still work, but image-only event recognition will be much weaker.

### 2. Start Backend

```bash
source venv/bin/activate
python app.py
```

You should see output like:

```text
EventRadar - FastAPI Service
Admin Page: http://localhost:5001/admin.html
Events Page: http://localhost:5001/events.html
API Docs:   http://localhost:5001/api/docs
```

Common pages:

| Page | Purpose |
|------|------|
| `http://localhost:5001/admin.html` | Admin panel for login, RSS, and API checks |
| `http://localhost:5001/login.html` | WeChat QR-code login |
| `http://localhost:5001/rss.html` | WeChat RSS subscription management |
| `http://localhost:5001/events.html` | Main EventRadar calendar UI |
| `http://localhost:5001/api/docs` | Swagger API docs |

### 3. Initialize the WeChat/RSS Foundation

Before using event extraction for the first time:

1. Open `login.html` and scan the QR code with a WeChat official account administrator.
2. Open `admin.html` or `rss.html`, search for accounts, and subscribe to the ones you want to monitor.
3. Trigger RSS polling and confirm articles are written into `data/rss.db`.
4. Generate a daily archive and confirm `data/daily_archives/YYYY-MM-DD/articles.json` plus the image directory exist.

Related API calls:

```bash
# Subscribe to an account. fakeid can be found through the search API or UI.
curl -X POST http://localhost:5001/api/rss/subscribe \
  -H "Content-Type: application/json" \
  -d '{"fakeid":"account fakeid","nickname":"account name"}'

# Poll subscribed accounts
curl -X POST http://localhost:5001/api/rss/poll

# Create today's article archive and download images
curl -X POST "http://localhost:5001/api/rss/archive/daily?poll=false&download_images=true"
```

### 4. Run Event Extraction

Open `events.html`, choose an account and date range, then run extraction. You can also call the API directly:

```bash
curl -X POST http://localhost:5001/api/events/extract \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-05-21",
    "use_llm": true,
    "use_vision": true,
    "max_chars": 9000
  }'
```

You can also run the full pipeline by account and date range:

```bash
curl -X POST http://localhost:5001/api/events/run-account-range \
  -H "Content-Type: application/json" \
  -d '{
    "account": "account name",
    "start_date": "2026-05-15",
    "end_date": "2026-05-21",
    "use_llm": true,
    "use_vision": true,
    "download_images": true
  }'
```

Outputs:

- Event store: `data/events.db`
- Daily JSON: `data/events/YYYY-MM-DD/events.json`
- CSV: `data/events/YYYY-MM-DD/events.csv`
- ICS: `data/events/YYYY-MM-DD/calendar.ics`
- Long-lived ICS: `http://localhost:5001/api/events/calendar.ics`

### 5. Enable Scheduled Automation

You can enable automation from the settings panel in `events.html`, or configure `.env`:

```env
EVENT_AUTOMATION_ENABLED=true
EVENT_AUTOMATION_TIME=09:07
EVENT_AUTOMATION_LOOKBACK_DAYS=0
EVENT_AUTOMATION_USE_LLM=true
EVENT_AUTOMATION_USE_VISION=true
EVENT_RETENTION_DAYS=15
```

Meaning:

- Poll automation-enabled accounts at the configured time every day.
- `EVENT_AUTOMATION_LOOKBACK_DAYS=0` means only today; a conservative free-mode setup should usually keep it at `0`, with occasional manual backfill.
- Each save triggers dedupe so repeated imports keep one record.
- Unfavorited old events are cleaned after the retention window; favorited events are always preserved.

Check progress:

```bash
curl http://localhost:5001/api/events/settings
```

The response includes `automation.progress`, and the frontend settings panel also displays the current stage and progress.

## Public Access

For local debugging, you can expose the service with Cloudflare Quick Tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:5001
```

It will return a URL like:

```text
https://example-words.trycloudflare.com
```

Then visit:

- `https://example-words.trycloudflare.com/events.html`
- `https://example-words.trycloudflare.com/admin.html`

You can also let `start.sh` launch the tunnel automatically:

```env
CLOUDFLARE_TUNNEL_ENABLED=true
PORT=5001
```

Then run:

```bash
bash start.sh
```

Cloudflare Quick Tunnel URLs are temporary and may change after restart. For production use, prefer a fixed domain and a formal tunnel.

## Docker

Build and run locally:

```bash
cp env.example .env
docker-compose up -d --build
docker-compose logs -f
```

The default port is controlled by `PORT` in `.env`. After the first launch, visit `login.html` to complete WeChat QR login.

If you use the original upstream image, note that it may not include EventRadar's latest event extraction and calendar features. Building from this repository is recommended.

## API Reference

### Health Check

```bash
curl http://localhost:5001/api/health
```

### WeChat Article Foundation

| Method | Path | Description |
|------|------|------|
| `GET` | `/api/public/searchbiz?query=keyword` | Search WeChat accounts and get fakeid |
| `POST` | `/api/article` | Parse one WeChat article |
| `POST` | `/api/rss/subscribe` | Add an account subscription |
| `GET` | `/api/rss/subscriptions` | List subscriptions |
| `POST` | `/api/rss/poll` | Manually poll account articles |
| `POST` | `/api/rss/archive/daily` | Create daily article archive |
| `GET` | `/api/rss/{fakeid}` | Serve RSS feed |

### Event Calendar

| Method | Path | Description |
|------|------|------|
| `POST` | `/api/events/extract` | Extract events from daily archives |
| `POST` | `/api/events/run-account` | Subscribe, poll, archive, and extract for one account |
| `POST` | `/api/events/run-account-range` | Run extraction by account and date range |
| `GET` | `/api/events/list` | Query events by date, status, priority, and keyword |
| `PATCH` | `/api/events/{event_id}` | Edit event content, status, and priority |
| `POST` | `/api/events/{event_id}/favorite` | Favorite or unfavorite an event |
| `GET` | `/api/events/calendar.ics` | Long-lived ICS calendar subscription |
| `GET` | `/api/events/export.csv` | Export CSV |
| `POST` | `/api/events/cleanup` | Clean up old unfavorited events |
| `POST` | `/api/events/cleanup-duplicates` | Manually remove duplicates |
| `GET` | `/api/events/settings` | Read automation settings and progress |
| `POST` | `/api/events/settings` | Save automation settings |

## Deduplication

When content is imported repeatedly, EventRadar deduplicates at the storage, list, and ICS layers:

- Records from the same source article, event title, or event date can reuse existing events.
- Higher-quality extracted content can update the stored record while preserving status, favorite, and notes.
- Favorite or confirmed state is migrated to the retained event.
- Duplicate cleanup runs automatically after extraction saves.
- Low-quality legacy records with empty time fields can be removed on startup or manual cleanup.

This means repeated daily imports should not produce multiple copies of the same calendar item.

## Calendar Time Rules

The calendar does not simply use `start_time`; it sorts by the earliest actionable time:

1. If signup start time exists, use it first.
2. If there is no signup start but a deadline exists, use the deadline.
3. Otherwise, use the event start time.
4. Deadline-like `May 10 24:00` is kept on May 10 instead of drifting to May 11.
5. Timezone-aware ISO timestamps are displayed on the correct local date.

## Configuration

Common settings:

| Key | Description | Default |
|--------|------|--------|
| `PORT` | Service port | `5000` |
| `HOST` | Bind host | `0.0.0.0` |
| `SITE_URL` | Image proxy and external URL | `http://localhost:5000` |
| `PUBLIC_URL` | Optional fixed public URL | empty |
| `WECHAT_TOKEN` / `WECHAT_COOKIE` | WeChat credentials filled after QR login | empty |
| `RSS_FETCH_FULL_CONTENT` | Whether RSS fetches full content | `true` |
| `WECHAT_FETCH_CONCURRENCY` | Full-content fetch concurrency; lower is safer | `1` |
| `WECHAT_FETCH_DELAY_MIN` / `WECHAT_FETCH_DELAY_MAX` | Random delay between full-content fetches, in seconds | `8` / `18` |
| `WECHAT_ACCOUNT_DELAY` | Delay between accounts, in seconds | `20` |
| `WECHAT_MAX_ARTICLES_PER_ACCOUNT` | Max full articles per account per poll | `10` |
| `WECHAT_VERIFICATION_PAUSE_MINUTES` | Cooldown minutes after verification is triggered | `60` |
| `WECHAT_VERIFICATION_STOP_THRESHOLD` | Verification threshold before cooldown | `1` |
| `WECHAT_PROXY_REQUIRED` | Require proxy pool before fetching full content | `false` |
| `DAILY_ARCHIVE_DOWNLOAD_IMAGES` | Download images during daily archive | `true` |
| `MINIMAX_API_KEY` | MiniMax Token Plan Key | empty |
| `MINIMAX_API_STYLE` | Text model API style | `anthropic` |
| `MINIMAX_BASE_URL` | Text model base URL | `https://api.minimax.io/anthropic` |
| `MINIMAX_API_HOST` | Vision endpoint host | `https://api.minimaxi.com` |
| `MINIMAX_MODEL` | Text extraction model | `MiniMax-M2.7` |
| `MINIMAX_VISION_ENABLED` | Enable vision understanding | `true` |
| `EVENT_AUTOMATION_ENABLED` | Enable scheduled event automation | `false` |
| `EVENT_AUTOMATION_LOOKBACK_DAYS` | Automation lookback days | `0` |
| `EVENT_RETENTION_DAYS` | Retention days for old unfavorited events | `15` |
| `PROXY_URLS` | SOCKS5/HTTP proxy pool | empty |
| `CLOUDFLARE_TUNNEL_ENABLED` | Whether `start.sh` launches Cloudflare Tunnel | `false` |

Anti-risk suggestions:

- When fetching full content, use 2-3 SOCKS5 proxies to reduce WeChat risk checks.
- Example: `PROXY_URLS=socks5://user:pass@ip1:1080,socks5://user:pass@ip2:1080`
- The default is a conservative free-mode setup: one scheduled run per day, `0-1` lookback days, and up to `10` full articles per account per poll.
- Conservative settings: `WECHAT_FETCH_CONCURRENCY=1`, `WECHAT_FETCH_DELAY_MIN=8`, `WECHAT_FETCH_DELAY_MAX=18`, `WECHAT_ACCOUNT_DELAY=20`.
- After proxies are stable, concurrency can be raised to `2`; staying above `3` long term is not recommended.
- If verification is triggered, the system enters a 60-minute cooldown, shows the remaining cooldown in settings, and stops the current scheduled run.

## Testing

```bash
PYTHONPYCACHEPREFIX=.pycache venv/bin/python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=.pycache venv/bin/python -m compileall -q app.py routes utils tests
```

## Data Directory

| Path | Description |
|------|------|
| `data/rss.db` | Account subscriptions and article cache |
| `data/events.db` | Event store |
| `data/daily_archives/YYYY-MM-DD/articles.json` | Daily article archive |
| `data/daily_archives/YYYY-MM-DD/images/` | Daily image archive |
| `data/events/YYYY-MM-DD/events.json` | Daily event export |
| `data/events/YYYY-MM-DD/calendar.ics` | Daily ICS export |
| `data/automation/` | Automation run history |

## Notes

- This project requires QR-code login with a WeChat official account administrator. Credentials usually expire after about 4 days.
- Chrome TLS fingerprinting, proxy rotation, random delays, account-level spacing, verification detection, and cooldown are built in; for bulk full-content fetching, a proxy pool and low concurrency are still recommended.
- Image-only articles depend on MiniMax Token Plan vision understanding. Without a key, only weak fallback rules are available.
- Quick Tunnel public URLs are temporary and not ideal for production.
- This project is for learning, research, and personal information organization. Please follow the relevant WeChat platform terms.

## Acknowledgements

EventRadar is developed on top of the original open-source **WeChat Download API** project, which provides the essential WeChat login, article fetching, RSS, image proxy, anti-risk, and FastAPI foundation. This project adds event extraction, vision understanding, an event store, calendar UI, ICS subscription, automation progress, favorite protection, retention cleanup, and repeated-import dedupe.

Thanks to:

- Original author [tmwgsicp](https://github.com/tmwgsicp) and the open-source `wechat-download-api`
- [FastAPI](https://fastapi.tiangolo.com/)
- [curl_cffi](https://github.com/lexiforest/curl_cffi)
- [HTTPX](https://www.python-httpx.org/)
- [MiniMax](https://www.minimaxi.com/)
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

## License

This project follows the original project's AGPL-3.0 license. If you modify it and provide it as a network service, please comply with AGPL-3.0 obligations.
