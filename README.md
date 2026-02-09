# Telegram 新闻推送（NYP / WaPo / Politico / Economist / WSJ / AP / The Atlantic / Reuters / SCMP）

这个程序会轮询 RSS，并把最新新闻推送到你的 Telegram。

## 1. 创建 Telegram Bot
1. 打开 Telegram，进入 `@BotFather`。
2. 发送 `/newbot`，按提示创建机器人。
3. 记录 `bot token`（形如 `123456:ABC...`）。
4. 打开你新建的机器人，点击 `Start`（这一步必须做，否则拿不到 chat_id）。

## 2. 获取 chat_id
在项目目录执行：

```bash
curl -s "https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates"
```

在返回 JSON 中找到：
- 私聊：`message.chat.id`（通常是纯数字）
- 群聊：`message.chat.id`（通常是负数）

把这个值填到 `.env` 的 `TELEGRAM_CHAT_ID`。

## 3. 安装并配置

```bash
cd /Users/oliverou/telegram-news-pusher
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

编辑 `.env`：
- `TELEGRAM_BOT_TOKEN`：你的 bot token
- `TELEGRAM_CHAT_ID`：你的 chat id

可选参数：
- `POLL_SECONDS`：轮询秒数（默认 120）
- `MAX_ITEMS_PER_SOURCE`：每轮每个媒体最多推送条数（默认 3）
- `BOOTSTRAP_SILENT=true`：首次运行只建立去重缓存，不推送历史消息
- `MAJOR_ONLY=true`：仅推送重大新闻（按关键词过滤，且排除 Opinion）
- `QUIET_HOUR_START=23`、`QUIET_HOUR_END=9`：23:00-09:00 夜间免打扰
- `NIGHT_DIGEST_MAX=40`：夜间汇总最多缓存 40 条，09:00 后自动逐条发送汇总

图片说明：
- 每条新闻默认用 RSS 自带图片发送
- 若 RSS 无图，会自动回退为对应媒体 logo，保证按图片消息推送

先做连通性测试：

```bash
cd /Users/oliverou/telegram-news-pusher
source .venv/bin/activate
python check_telegram.py
```

## 4. 启动

```bash
cd /Users/oliverou/telegram-news-pusher
source .venv/bin/activate
python news_notifier.py
```

## 5. 后台运行（macOS，推荐）
可用 `launchd` 常驻运行（下面示例路径按你的用户名写好）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.oliverou.telegram-news-pusher</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/oliverou/telegram-news-pusher/.venv/bin/python</string>
    <string>/Users/oliverou/telegram-news-pusher/news_notifier.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/oliverou/telegram-news-pusher</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/oliverou/telegram-news-pusher/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/oliverou/telegram-news-pusher/stderr.log</string>
</dict>
</plist>
```

保存为：
`~/Library/LaunchAgents/com.oliverou.telegram-news-pusher.plist`

加载：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.oliverou.telegram-news-pusher.plist
launchctl enable gui/$(id -u)/com.oliverou.telegram-news-pusher
launchctl kickstart -k gui/$(id -u)/com.oliverou.telegram-news-pusher
```

停止：

```bash
launchctl bootout gui/$(id -u)/com.oliverou.telegram-news-pusher
```

## 数据来源说明
为保证 9 家媒体都能稳定接入，程序默认使用 Google News 的站点 RSS 搜索（按域名过滤），来源仍然是对应媒体站点链接。

## 6. 免费云端常驻（GitHub Actions）
适合笔记本合盖/关机后继续推送。每 5 分钟运行一次，不需要自购服务器。

### 6.1 准备仓库
把 `/Users/oliverou/telegram-news-pusher` 推到一个 GitHub 仓库（建议公开仓库，免费额度更稳）。

### 6.2 配置 GitHub Secrets / Variables
仓库 `Settings -> Secrets and variables -> Actions`：

- `Secrets`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
- `Variables`
  - `NEWS_TZ`（例如 `America/Los_Angeles` 或 `Asia/Shanghai`）

### 6.3 启动工作流
仓库里已包含：
- `.github/workflows/news-bot.yml`
- `.state.cloud.json`

进入 `Actions -> Telegram News Bot`，手动点一次 `Run workflow` 完成首轮初始化，后续会按 cron 自动运行。
