# Project State (Stable + Beta)

Last updated: 2026-02-15

## 1) Repository Topology
- Stable repo: `https://github.com/zixuouoscaroliver/Oscar-Oliver`
- Beta repo: `https://github.com/zixuouoscaroliver/Oscar-Oliver-beta`
- Local path: `/Users/oliverou/telegram-news-pusher`

## 2) Branch Strategy
- Stable repo
- `main`: development
- `bot-stable`: stable runtime branch for production bot runs
- `bot-state`: state-only branch (`.state.cloud.json`, `.mac.heartbeat.json`)

- Beta repo
- `main`: beta development + latest feature integration
- `bot-beta`: beta runtime branch for scheduled/manual bot runs
- `bot-state`: state-only branch

Runtime selection priority in workflow (`news-bot.yml`):
1. manual dispatch input `ref`
2. repo variable `BOT_CODE_REF`
3. fallback default in workflow (`bot-stable`)

Current beta runtime is expected to use:
- `BOT_CODE_REF=bot-beta`

## 3) Workflows and Purpose
- `.github/workflows/news-bot.yml`
- Main run loop (`python news_notifier.py --once`)
- Scheduled every 10 minutes
- Reads/writes bot state via `bot-state` branch

- `.github/workflows/version-trace.yml`
- Version iteration trace
- On push to runtime/dev branches, creates `trace-*` tags
- Uses GitHub API to create tag refs (not `git push tag`)

- `.github/workflows/beta-summary-preview.yml` (beta validation helper)
- Sends a 12-item synthetic grouped summary to Telegram
- Used to validate summary formatting quickly

- `.github/workflows/beta-single-preview.yml` (beta validation helper)
- Sends one synthetic single-news message
- Used to validate single-item render format

## 4) Required Secrets / Variables
Settings path: `Settings -> Secrets and variables -> Actions`

### Required Secrets
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Optional Secrets
- `OPENAI_API_KEY`
- If missing, summary path still works with rule-based summarization.

### Variables
- `BOT_CODE_REF`
- Stable repo recommended: `bot-stable`
- Beta repo recommended: `bot-beta`
- `NEWS_TZ` (e.g., `Asia/Shanghai`)
- `PRIMARY_HEARTBEAT_MAX_AGE_SECONDS` (default `900`)
- `AI_SUMMARY_THRESHOLD` (default `10`)
- `AI_SUMMARY_MODEL` (default `gpt-5-mini`)
- `AI_SUMMARY_MAX_ITEMS` (default `30`)

## 5) Current Feature Behavior

### 5.1 Image Fallback Chain
For each news item:
1. RSS image
2. article extracted image (`og:image`/`twitter:image`)
3. source logo fallback (`clearbit`/favicon)
4. default placeholder image
5. fallback to text `sendMessage` if all image sends fail

### 5.2 Compact Summary Trigger
When `new_items > AI_SUMMARY_THRESHOLD`:
- send one compact summary message instead of many single messages
- with `OPENAI_API_KEY`: AI summary path
- without key / AI failure: deterministic rule summary path

### 5.3 Summary Presentation (Current)
- grouped by topic category
- categories ordered by average heat (desc)
- items inside category ordered by per-item heat (desc)
- each headline is clickable (`HTML <a href=...>`)
- each headline displays heat marker: `🔥x.x`

### 5.4 Single Item Presentation (Current)
Single item caption header:
- `[Source] 🔥x.x`
Then title + published time + link.

## 6) Heat Score Model (Current)
Used by both single-item display and summary ranking.

Formula:
- `heat = source_weight + title_signal_weight + recency_weight + numeric_event_bonus`

Components:
- source weight: table in `news_notifier.py` (`SOURCE_HEAT_WEIGHT`)
- title signal: keyword buckets in `HEAT_SIGNAL_WEIGHTS`
- recency weight: based on age from published timestamp
- numeric bonus: +0.8 if title contains large number (`\\b\\d{3,}\\b`)

Sorting rules:
- Intra-category: item heat descending
- Inter-category: average category heat descending

## 7) State and Idempotency
- runtime state file: `.state.cloud.json`
- state branch persistence: `bot-state`
- dedup via `seen` map + TTL (`SEEN_TTL_HOURS`)

## 8) Operations Checklist
Before claiming runtime healthy:
1. confirm run on expected code ref (`code_ref=...`)
2. confirm summary metrics line exists
- `summary ... new=... pushed_ok=... pushed_fail=...`
3. if `new>0` and `pushed_ok=0`, check Telegram side config/permissions first

## 9) Version Iteration Trace Visibility
Trace tags are visible in repo Tags pages:
- stable: `https://github.com/zixuouoscaroliver/Oscar-Oliver/tags`
- beta: `https://github.com/zixuouoscaroliver/Oscar-Oliver-beta/tags`

Tag format:
- `trace-<branch>-<UTC timestamp>-<short sha>`

## 10) Promotion Rule (Beta -> Stable)
Recommended sequence:
1. run beta and observe stability window
2. confirm bot output format / delivery / error rate
3. fast-forward or cherry-pick validated commits into stable
4. trigger stable run and verify summary metrics

