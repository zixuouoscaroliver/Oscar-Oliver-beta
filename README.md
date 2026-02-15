# Telegram News Pusher (Stable)

稳定版仓库：`zixuouoscaroliver/Oscar-Oliver`

这是生产使用的稳定线，负责把多家英文媒体新闻推送到 Telegram。

## 当前能力
- 多源抓取：NYP / WaPo / Politico / Economist / WSJ / AP / The Atlantic / Reuters / SCMP
- 推送策略：优先发 `sendPhoto`（带标题/链接），图片不可用时自动回退
- 去重与状态：基于 `.state.cloud.json` + `SEEN_TTL_HOURS` 去重
- 重大新闻筛选：`MAJOR_ONLY=true` 时仅推送命中 `MAJOR_KEYWORDS` 的新闻（并排除 Opinion）
- 免打扰与晨间汇总：`QUIET_HOUR_START`~`QUIET_HOUR_END` 缓存，白天自动补发
- 云端定时运行：GitHub Actions 每 10 分钟执行一次 `python news_notifier.py --once`
- 主备机制：若检测到主机心跳 `.mac.heartbeat.json` 新鲜，Actions 自动跳过
- 状态持久化：状态写入 `bot-state` 分支，不污染主开发分支

## 仓库分支约定（稳定版）
- `main`：开发分支
- `bot-stable`：稳定运行分支（Actions 默认运行此分支）
- `bot-state`：仅存储状态文件（`.state.cloud.json` / `.mac.heartbeat.json`）

## GitHub Actions 必填配置
路径：`Settings -> Secrets and variables -> Actions`

### Secrets
- `TELEGRAM_BOT_TOKEN`：稳定版 bot token
- `TELEGRAM_CHAT_ID`：稳定版接收 chat id

### Variables
- `NEWS_TZ`：时区（例如 `Asia/Shanghai`）
- `PRIMARY_HEARTBEAT_MAX_AGE_SECONDS`：主机心跳阈值（默认 900）
- `BOT_CODE_REF`：可选；不填则 workflow 默认 `bot-stable`

## 本地运行（可选）
```bash
cd /Users/oliverou/telegram-news-pusher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 填写 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
python check_telegram.py
python news_notifier.py --once
```

## 运维观察点
- 工作流文件：`.github/workflows/news-bot.yml`
- 关键日志：`summary ... new=... pushed_ok=... pushed_fail=...`
- 若 `new>0` 且 `pushed_ok=0`，通常是 Telegram 配置问题（token/chat_id 权限或目标会话不可达）

## Beta 说明
测试线在独立仓库：`zixuouoscaroliver/Oscar-Oliver-beta`，用于实验改动，不影响本稳定版。
