<p align="center">
  <img src="imgs/EventRadar.png" alt="EventRadar" width="680">
</p>

<p align="center">
  <strong>多平台活动雷达：从公众号、链接、文本和图片里自动发现活动，读图补全信息，去重入库，并生成可订阅的大日历。</strong>
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
  微信文章抓取 · 每日归档 · 图片理解 · 活动抽取 · 去重入库 · 日历订阅 · 定时自动化
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="#为什么选择-eventradar">为什么选择</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#当前能力">当前能力</a> ·
  <a href="#架构">架构</a> ·
  <a href="#常用-api">API</a> ·
  <a href="#配置说明">配置</a>
</p>

## 为什么选择 EventRadar

EventRadar 是一个面向“活动情报收集”的完整本地化工具。当前版本以微信公众号文章抓取、RSS 订阅和图片归档为主要信息源，并预留多平台扩展方向，后续可以接入小红书、网页链接、社群文本、活动海报等来源。它进一步加入 MiniMax 图片理解、活动结构化抽取、日历去重、收藏保护、定时自动化和 ICS 订阅，适合跟踪讲座、比赛、报名、路演、开放日、峰会、黑客松等信息。

本项目是在开源项目 **WeChat Download API** 的基础上继续开发而来。原项目提供了微信公众号登录、文章抓取、RSS 订阅、反风控和图片代理等底层能力；EventRadar 在此基础上扩展成一个以“活动日历”为核心的新项目。感谢原作者和原项目的开源工作，相关致谢见文末。

| 活动信息收集的常见痛点 | EventRadar 的处理方式 |
| --- | --- |
| 活动信息散落在公众号文章、海报、链接和文本里 | 把多来源内容统一归档，再抽取成结构化活动 |
| 纯图片海报难以搜索、复制和整理 | 使用 MiniMax 图片理解读取活动名称、时间、地点、报名方式和主办方 |
| 重复导入容易让日历变乱 | 在入库、列表和 ICS 层共同去重，并迁移收藏/确认状态 |
| 活动开始、报名开始、报名截止混在一起 | 优先用“最早需要行动的关键时间”放入日历 |
| 手工维护日历成本高 | 支持定时轮询、自动归档、自动抽取、过期清理和 ICS 订阅 |

EventRadar 的底层组合：

- **FastAPI 运行时**：静态页面、API 路由、启动任务和健康检查。
- **微信与 RSS 基座**：登录、公众号搜索、订阅、轮询、文章解析和图片代理。
- **每日归档管线**：按日期保存文章与图片。
- **活动抽取管线**：MiniMax + 规则兜底，把正文和图片理解结果转成活动。
- **SQLite 活动库**：去重、状态、分级、收藏、清理、CSV 和 ICS。
- **浏览器日历 UI**：审核、筛选、编辑、手动添加、设置和自动化进度。

## 当前能力

| 模块 | 能力 |
| --- | --- |
| **🔐 公众号与 RSS** | 扫码登录、搜索公众号、订阅、轮询、文章列表和完整正文抓取。 |
| **🗂️ 每日归档** | 生成 `data/daily_archives/YYYY-MM-DD/articles.json`，并下载封面和正文图片。 |
| **👁️ 图片理解** | 通过 MiniMax Token Plan 图片理解接口读取纯图片海报里的活动信息。 |
| **🧠 活动抽取** | 合并正文文本和图片理解结果，用大模型与规则兜底抽取结构化活动。 |
| **⏱️ 日历优先时间** | 当报名开始或报名截止早于活动开始时，优先显示这些更早需要行动的时间。 |
| **🧹 重复导入去重** | 重复跑同一天、同公众号或同一篇文章时，只保留一条活动记录，并迁移审核状态。 |
| **⭐ 活动库管理** | 支持 `pending` / `confirmed` / `ignored` 状态、`S/A/B/C` 分级、收藏保护和过期清理。 |
| **🗓️ 活动日历 UI** | 支持筛选、月/周/列表视图、当天弹窗、编辑、收藏和手动添加。 |
| **📤 ICS 与 CSV 导出** | 提供 `/api/events/calendar.ics` 长期订阅和 CSV 导出。 |
| **⚙️ 定时自动化** | 自动轮询、归档、读图、抽取、去重、入库，并在页面展示进度。 |
| **🌐 公网访问** | 可配合 `cloudflared` 生成临时 `trycloudflare.com` 公网地址。 |

## 架构

<p align="center">
  <img src="imgs/framework_CN.png" alt="EventRadar 架构图" width="820">
</p>

> 上方架构图展示了主要运行层级和数据流。更细的模块职责集中在 `app.py`、`routes/`、`utils/`、`static/` 和 `data/` 中。


## 快速开始

下面是推荐的完整启动方式。因为 EventRadar 依赖原项目的微信公众号登录、RSS 订阅和文章抓取能力，所以启动后先完成“基座”部分，再使用活动日历。

```text
创建环境 -> 启动后端 -> 微信扫码登录 -> 订阅公众号 -> RSS 轮询 -> 归档文章/图片 -> 抽取活动 -> 审核日历 -> 订阅 ICS
```

### 1. 创建环境

```bash
cd /path/to/eventradar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

编辑 `.env`，至少确认这些配置：

```env
PORT=5001
HOST=0.0.0.0
DAILY_ARCHIVE_TIMEZONE=Asia/Shanghai
DAILY_ARCHIVE_DOWNLOAD_IMAGES=true

MINIMAX_API_KEY=你的 MiniMax Token Plan Key
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

说明：

- `MINIMAX_MODEL` 用于文本结构化抽取。
- 图片理解走 Token Plan 的 `/v1/coding_plan/vlm`，优先使用 `MINIMAX_API_HOST`，代码会在 `api.minimaxi.com` 和 `api.minimax.io` 间自动回退。
- 如果暂时没有 MiniMax Key，系统仍会用规则兜底，但纯图片活动识别会明显变弱。

### 2. 启动后端

```bash
source venv/bin/activate
python app.py
```

启动后会看到类似：

```text
EventRadar - FastAPI Service
Admin Page: http://localhost:5001/admin.html
Events Page: http://localhost:5001/events.html
API Docs:   http://localhost:5001/api/docs
```

常用页面：

| 页面 | 用途 |
|------|------|
| `http://localhost:5001/admin.html` | 原项目管理面板：登录、RSS、接口测试 |
| `http://localhost:5001/login.html` | 微信公众平台扫码登录 |
| `http://localhost:5001/rss.html` | 公众号 RSS 订阅管理 |
| `http://localhost:5001/events.html` | EventRadar 活动日历主界面 |
| `http://localhost:5001/api/docs` | Swagger API 文档 |

### 3. 先启动“原项目基座能力”

第一次使用必须先完成以下步骤：

1. 打开 `login.html`，用公众号管理员微信扫码登录。
2. 打开 `admin.html` 或 `rss.html`，搜索并订阅需要监控的公众号。
3. 手动触发 RSS 轮询，确认文章能进入 `data/rss.db`。
4. 生成每日归档，确认 `data/daily_archives/YYYY-MM-DD/articles.json` 和图片目录存在。

对应 API：

```bash
# 订阅公众号，fakeid 可从搜索接口或页面获取
curl -X POST http://localhost:5001/api/rss/subscribe \
  -H "Content-Type: application/json" \
  -d '{"fakeid":"公众号 fakeid","nickname":"公众号名称"}'

# 轮询已订阅公众号
curl -X POST http://localhost:5001/api/rss/poll

# 生成当天文章归档并下载图片
curl -X POST "http://localhost:5001/api/rss/archive/daily?poll=false&download_images=true"
```

### 4. 再运行活动抽取

打开 `events.html`，选择公众号和日期范围后运行。也可以用 API：

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

也可以按公众号和日期范围跑完整链路：

```bash
curl -X POST http://localhost:5001/api/events/run-account-range \
  -H "Content-Type: application/json" \
  -d '{
    "account": "去探索官方号",
    "start_date": "2026-05-15",
    "end_date": "2026-05-21",
    "use_llm": true,
    "use_vision": true,
    "download_images": true
  }'
```

产物：

- 活动库：`data/events.db`
- 每日导出：`data/events/YYYY-MM-DD/events.json`
- CSV：`data/events/YYYY-MM-DD/events.csv`
- ICS：`data/events/YYYY-MM-DD/calendar.ics`
- 长期 ICS：`http://localhost:5001/api/events/calendar.ics`

### 5. 开启定时自动化

在 `events.html` 的设置里可以开启，也可以编辑 `.env`：

```env
EVENT_AUTOMATION_ENABLED=true
EVENT_AUTOMATION_TIME=09:07
EVENT_AUTOMATION_LOOKBACK_DAYS=0
EVENT_AUTOMATION_USE_LLM=true
EVENT_AUTOMATION_USE_VISION=true
EVENT_RETENTION_DAYS=15
```

含义：

- 每天到点后自动轮询已启用自动抓取的公众号。
- `EVENT_AUTOMATION_LOOKBACK_DAYS=0` 表示只抓今天；免费保守模式建议长期保持 `0`，偶尔补抓可临时改成 `1`。
- 每次保存后会自动去重，重复导入只保留一条。
- 未收藏且早于当前日期 15 天前的活动会自动清理；收藏活动永远保留。

查看进度：

```bash
curl http://localhost:5001/api/events/settings
```

返回里会包含 `automation.progress`，前端设置区也会显示当前阶段和进度。

## 公网访问

本地调试时可以使用 Cloudflare Quick Tunnel：

```bash
cloudflared tunnel --url http://127.0.0.1:5001
```

启动后会得到类似：

```text
https://example-words.trycloudflare.com
```

访问：

- `https://example-words.trycloudflare.com/events.html`
- `https://example-words.trycloudflare.com/admin.html`

也可以让 `start.sh` 自动启动 tunnel：

```env
CLOUDFLARE_TUNNEL_ENABLED=true
PORT=5001
```

然后：

```bash
bash start.sh
```

注意：Cloudflare Quick Tunnel 地址是临时地址，重启后可能变化。生产环境建议使用固定域名和正式 tunnel。

## Docker 启动

当前仓库可以直接本地构建：

```bash
cp env.example .env
docker-compose up -d --build
docker-compose logs -f
```

默认端口由 `.env` 的 `PORT` 控制。首次使用后仍需访问 `login.html` 扫码登录。

如果你只是使用原项目官方镜像，请注意官方镜像不一定包含 EventRadar 的最新活动抽取和日历功能；推荐使用本仓库构建镜像。

## 常用 API

| 分组 | 入口 |
| --- | --- |
| **🩺 健康检查** | `/api/health` |
| **🔐 公众号基座** | `/api/public/searchbiz`、`/api/article`、`/api/rss/*` |
| **🗓️ 活动日历** | `/api/events/extract`、`/api/events/list`、`/api/events/calendar.ics`、`/api/events/settings` |

### 健康检查

```bash
curl http://localhost:5001/api/health
```

### 微信公众号文章基座

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/public/searchbiz?query=关键词` | 搜索公众号，获取 fakeid |
| `POST` | `/api/article` | 解析单篇微信文章 |
| `POST` | `/api/rss/subscribe` | 添加公众号订阅 |
| `GET` | `/api/rss/subscriptions` | 查看订阅列表 |
| `POST` | `/api/rss/poll` | 手动轮询公众号文章 |
| `POST` | `/api/rss/archive/daily` | 生成每日文章归档 |
| `GET` | `/api/rss/{fakeid}` | 输出 RSS 订阅源 |

### 活动日历

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/events/extract` | 从每日归档抽取活动 |
| `POST` | `/api/events/run-account` | 输入公众号后完成订阅、轮询、归档、抽取 |
| `POST` | `/api/events/run-account-range` | 按公众号和日期范围批量抽取 |
| `GET` | `/api/events/list` | 查询活动库，支持日期、状态、分级、关键词 |
| `PATCH` | `/api/events/{event_id}` | 编辑活动、状态、分级 |
| `POST` | `/api/events/{event_id}/favorite` | 收藏/取消收藏 |
| `GET` | `/api/events/calendar.ics` | 长期活动日历订阅 |
| `GET` | `/api/events/export.csv` | 导出 CSV |
| `POST` | `/api/events/cleanup` | 清理超过保留期的未收藏活动 |
| `POST` | `/api/events/cleanup-duplicates` | 手动清理重复活动 |
| `GET` | `/api/events/settings` | 查看自动化配置和进度 |
| `POST` | `/api/events/settings` | 保存自动化配置 |

## 去重规则

重复导入时，系统会在入库层、列表层和 ICS 层共同去重：

- 同一来源文章、同一活动标题或同一活动日期会复用已有记录。
- 新抽取质量更高时会更新原记录内容，但保留原来的状态、收藏、备注。
- 如果重复项里有收藏或确认状态，会迁移到保留的那一条。
- 每次抽取保存后自动执行重复清理。
- 历史数据中残留的低质量空时间记录会在启动或手动清理时移除。

这意味着每天重复跑导入不会让日历上出现多条相同活动。

## 时间规则

活动日历的日期不是简单使用 `start_time`，而是按“最早需要行动的关键时间”排序：

1. 如果有报名开始时间，优先使用报名开始。
2. 如果没有报名开始，但有报名截止，使用报名截止。
3. 否则使用活动开始时间。
4. 识别到 `5月10日晚上24:00` 这类截止时间时，会归到 `5月10日`，不会漂到 `5月11日`。
5. 带时区的 ISO 时间，例如 `2026-05-23T13:30:00+08:00`，会按本地日期正确显示在 5月23日。

## 配置说明

大多数部署优先关注四类配置：服务地址、微信凭证、MiniMax 抽取和自动化节奏。

常用配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `PORT` | 服务端口 | `5000` |
| `HOST` | 监听地址 | `0.0.0.0` |
| `SITE_URL` | 图片代理和外部访问地址 | `http://localhost:5000` |
| `PUBLIC_URL` | 固定公网地址，可选 | 空 |
| `WECHAT_TOKEN` / `WECHAT_COOKIE` | 微信登录凭证，扫码后自动填充 | 空 |
| `RSS_FETCH_FULL_CONTENT` | RSS 是否抓取完整正文 | `true` |
| `WECHAT_FETCH_CONCURRENCY` | 微信正文抓取并发，越低越稳 | `1` |
| `WECHAT_FETCH_DELAY_MIN` / `WECHAT_FETCH_DELAY_MAX` | 单篇正文抓取之间的随机等待区间，秒 | `8` / `18` |
| `WECHAT_ACCOUNT_DELAY` | 每个公众号之间的等待时间，秒 | `20` |
| `WECHAT_MAX_ARTICLES_PER_ACCOUNT` | 每个公众号每轮最多抓取完整正文数 | `10` |
| `WECHAT_VERIFICATION_PAUSE_MINUTES` | 连续触发验证后的自动冷却分钟数 | `60` |
| `WECHAT_VERIFICATION_STOP_THRESHOLD` | 连续触发几次验证后进入冷却 | `1` |
| `WECHAT_PROXY_REQUIRED` | 是否强制要求配置代理池后才抓正文 | `false` |
| `DAILY_ARCHIVE_DOWNLOAD_IMAGES` | 每日归档是否下载图片 | `true` |
| `MINIMAX_API_KEY` | MiniMax Token Plan Key | 空 |
| `MINIMAX_API_STYLE` | 文本模型接口风格 | `anthropic` |
| `MINIMAX_BASE_URL` | 文本模型接口地址 | `https://api.minimax.io/anthropic` |
| `MINIMAX_API_HOST` | Token Plan 图片理解接口 host | `https://api.minimaxi.com` |
| `MINIMAX_MODEL` | 文本抽取模型 | `MiniMax-M2.7` |
| `MINIMAX_VISION_ENABLED` | 是否启用图片理解 | `true` |
| `EVENT_AUTOMATION_ENABLED` | 是否启用定时活动抓取 | `false` |
| `EVENT_AUTOMATION_LOOKBACK_DAYS` | 定时任务回看天数 | `0` |
| `EVENT_RETENTION_DAYS` | 未收藏过期活动保留天数 | `15` |
| `PROXY_URLS` | SOCKS5/HTTP 代理池 | 空 |
| `CLOUDFLARE_TUNNEL_ENABLED` | `start.sh` 是否启动 Cloudflare Tunnel | `false` |

防风控建议：

- 启用完整正文抓取时，建议配置 2-3 个 SOCKS5 代理，降低微信风控概率。
- 示例：`PROXY_URLS=socks5://user:pass@ip1:1080,socks5://user:pass@ip2:1080`
- 默认即为免费保守模式：每天定时跑 1 次，回看天数建议 `0-1`，每个公众号每轮最多抓取 `10` 篇正文。
- 保守配置：`WECHAT_FETCH_CONCURRENCY=1`，`WECHAT_FETCH_DELAY_MIN=8`，`WECHAT_FETCH_DELAY_MAX=18`，`WECHAT_ACCOUNT_DELAY=20`。
- 代理稳定后可把并发调到 `2`；不建议长期超过 `3`。
- 如果触发微信验证，系统会自动进入 60 分钟冷却，设置页会显示剩余冷却时间；冷却期间定时抓取会停止本轮任务。

## 测试

```bash
PYTHONPYCACHEPREFIX=.pycache venv/bin/python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=.pycache venv/bin/python -m compileall -q app.py routes utils tests
```

## 数据目录

| 路径 | 说明 |
|------|------|
| `data/rss.db` | 公众号订阅和文章缓存 |
| `data/events.db` | 活动库 |
| `data/daily_archives/YYYY-MM-DD/articles.json` | 每日文章归档 |
| `data/daily_archives/YYYY-MM-DD/images/` | 每日图片归档 |
| `data/events/YYYY-MM-DD/events.json` | 每日活动导出 |
| `data/events/YYYY-MM-DD/calendar.ics` | 每日 ICS |
| `data/automation/` | 自动化运行历史 |

## 注意事项

- 本项目需要微信公众号管理员扫码登录，凭证通常约 4 天过期，过期后需重新登录。
- 项目已内置 Chrome TLS 指纹、代理池轮转、随机等待、公众号间隔、验证检测和自动冷却；批量抓取完整正文时仍建议配置代理池，并保持低并发。
- 纯图片文章依赖 MiniMax Token Plan 图片理解能力；没有 Key 时只能做弱规则兜底。
- Quick Tunnel 公网地址是临时地址，不适合长期生产使用。
- 本项目仅供学习、研究和个人信息整理使用，请遵守微信公众平台相关服务条款。

## 致谢

EventRadar 基于原开源项目 **WeChat Download API** 继续开发。原项目提供了非常重要的微信公众号登录、文章抓取、RSS、图片代理、反风控和 FastAPI 基础架构。本项目在此基础上加入活动抽取、图片理解、活动库、日历 UI、ICS 订阅、自动化进度、收藏保护、过期清理和重复导入去重等能力。

感谢：

- 原项目作者 [tmwgsicp](https://github.com/tmwgsicp) 及其开源的 `wechat-download-api`
- [FastAPI](https://fastapi.tiangolo.com/)
- [curl_cffi](https://github.com/lexiforest/curl_cffi)
- [HTTPX](https://www.python-httpx.org/)
- [MiniMax](https://www.minimaxi.com/)
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

## License

本项目延续原项目的 AGPL-3.0 开源协议。修改后对外提供网络服务时，请遵守 AGPL-3.0 的开源义务。
