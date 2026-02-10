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
适合笔记本合盖/关机后继续推送。默认每 10 分钟运行一次，不需要自购服务器。

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

### 6.4 版本存档 / 回滚（推荐）
为避免 `main` 分支的改动导致定时任务跑不起来，Actions 默认运行稳定引用（默认 `bot-stable`），并且在 `bot-stable` 更新时自动打归档 tag。

- 稳定分支：`bot-stable`（线上运行用，确认可跑再更新）
- 开发分支：`main`（日常开发用）
- 运行引用优先级（从高到低）：
  - 手动 `Run workflow` 填写 `ref`
  - 仓库变量 `BOT_CODE_REF`（`Settings -> Secrets and variables -> Actions -> Variables`）
  - 默认 `bot-stable`

发布 / 回滚：
- 发布新版本：把确认可跑的提交合并/快进到 `bot-stable`，推送后会自动生成 tag：`bot-archive-YYYYMMDD-HHMMSS`
- 回滚到旧版本：把 `BOT_CODE_REF` 改成某个 `bot-archive-...` tag（或 commit SHA），下一次定时运行就会跑老版本

## 7. 维护与排障（建议先读）

Actions 页面：
- `https://github.com/zixuouoscaroliver/Oscar-Oliver/actions`

云端运行说明：
- 工作流：`.github/workflows/news-bot.yml`
- 运行方式：`python news_notifier.py --once`（Actions 默认每 10 分钟跑一次）
- 状态文件：`.state.cloud.json`（由 Actions 自动提交更新，用于去重和夜间汇总）

### 7.1 不推送/推送少（最常见原因）
- 没有命中重大关键词：`MAJOR_ONLY=true` 时只发命中 `MAJOR_KEYWORDS` 的标题
- 在免打扰时段：23:00-09:00（按 `NEWS_TZ` 时区），新闻会进入夜间汇总缓存，09:00 后发送
- Actions 失败：打开 Actions 页面看最新 run 是否绿色，点进去看失败步骤

### 7.2 常见修改点
- 修改 cron 频率：`.github/workflows/news-bot.yml` 的 `schedule.cron`
- 修改关键词/免打扰/夜间汇总：`.github/workflows/news-bot.yml` 的 `env`
- 调整配图清晰度：`news_notifier.py` 的 `normalize_image_url()`
- 修改数据源：`news_notifier.py` 的 `SOURCE_FEEDS`

### 7.3 重要安全说明（token 不写进 README）
- Telegram 与 GitHub 的凭据不要写进仓库文件。
- Telegram：在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 里改 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`。
- 时区：在同处 Variables 改 `NEWS_TZ`（例如 `Asia/Shanghai`）。
- 本机 git push 免输密码：凭据保存在 macOS Keychain（不是 README）。

### 7.4 本地更新维护（给 Codex 用）
维护目录：`/Users/oliverou/Oscar-Oliver`

建议每次修改前先备份：
```bash
cd /Users/oliverou/Oscar-Oliver
./backup_version.sh
```

修改并推送：
```bash
cd /Users/oliverou/Oscar-Oliver
git status
git add -A
git commit -m "your message"
# 云端会自动提交 .state.cloud.json，push 前偶尔需要先同步：
git fetch origin main
git rebase origin/main
git push origin main
```
