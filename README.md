# Telegram News Pusher (Beta)

Beta 仓库：`zixuouoscaroliver/Oscar-Oliver-beta`

这是实验线，用于验证新策略/新配置。功能上与稳定版同源，但允许更快迭代，可能出现推送波动或行为变化。

## 当前能力
- 多源抓取：NYP / WaPo / Politico / Economist / WSJ / AP / The Atlantic / Reuters / SCMP
- 推送策略：优先 `sendPhoto`，失败后回退 `sendMessage`
- 去重与状态：`.state.cloud.json` + `SEEN_TTL_HOURS`
- 重大新闻筛选：`MAJOR_ONLY=true` + `MAJOR_KEYWORDS`
- 免打扰与晨间汇总：`QUIET_HOUR_START`~`QUIET_HOUR_END` + `night_buffer`
- GitHub Actions 定时执行：每 10 分钟运行一次 `python news_notifier.py --once`
- 状态写回：提交到 `bot-state` 分支

## 分支约定（Beta）
- `main`：开发与工作流入口分支
- `bot-beta`：beta 运行分支（建议通过 `BOT_CODE_REF=bot-beta` 固定）
- `bot-state`：状态分支（自动维护）

## GitHub Actions 配置（Beta）
路径：`Settings -> Secrets and variables -> Actions`

### Secrets
- `TELEGRAM_BOT_TOKEN`：beta bot token
- `TELEGRAM_CHAT_ID`：beta chat id（必须是该 bot 有权限发送的会话）

### Variables
- `BOT_CODE_REF=bot-beta`（推荐固定，避免误跑到其他分支）
- `NEWS_TZ`（可选）
- `PRIMARY_HEARTBEAT_MAX_AGE_SECONDS`（可选）

## 验证是否工作正常
在 Actions 日志中重点看两行：
- `code_ref=bot-beta`
- `summary ... new=... pushed_ok=... pushed_fail=...`

若出现 `new>0` 且 `pushed_ok=0`，通常是 Telegram 目标配置问题（chat_id 不可达、bot 未在群/频道内、未给发送权限等）。

## 与稳定版关系
- 稳定版仓库：`zixuouoscaroliver/Oscar-Oliver`
- 建议流程：先在 Beta 验证，再把已验证改动同步到稳定版
