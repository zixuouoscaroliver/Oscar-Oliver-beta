#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path


def load_dotenv_simple(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def telegram_api_json(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def main() -> None:
    load_dotenv_simple()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        raise SystemExit("缺少 TELEGRAM_BOT_TOKEN")
    if not chat_id:
        raise SystemExit("缺少 TELEGRAM_CHAT_ID")

    me = telegram_api_json(token, "getMe", {})
    if not me.get("ok"):
        raise SystemExit(f"getMe 失败: {me}")

    test = telegram_api_json(
        token,
        "sendMessage",
        {"chat_id": chat_id, "text": "✅ Telegram 新闻推送测试成功"},
    )
    if not test.get("ok"):
        raise SystemExit(f"sendMessage 失败: {test}")

    print("Bot 可用，测试消息已发送。")


if __name__ == "__main__":
    main()
