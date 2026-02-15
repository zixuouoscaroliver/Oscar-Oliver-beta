#!/usr/bin/env python3
import argparse
import json
import logging
import os
import re
import subprocess
import time
import html
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SOURCE_DOMAINS = {
    "NYP": "nypost.com",
    "WaPo": "washingtonpost.com",
    "Politico": "politico.com",
    "Economist": "economist.com",
    "WSJ": "wsj.com",
    "AP NEWS": "apnews.com",
    "The Atlantic": "theatlantic.com",
    "Reuters": "reuters.com",
    "SCMP": "scmp.com",
}

SOURCE_FEEDS = {
    "NYP": "https://nypost.com/feed/",
    "WaPo": "https://feeds.washingtonpost.com/rss/world",
    "Politico": "https://rss.politico.com/politics-news.xml",
    "Economist": "https://www.bing.com/news/search?q=site%3Aeconomist.com&format=rss",
    "WSJ": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "AP NEWS": "https://www.bing.com/news/search?q=site%3Aapnews.com&format=rss",
    "The Atlantic": "https://www.theatlantic.com/feed/channel/news/",
    "Reuters": "https://www.bing.com/news/search?q=site%3Areuters.com&format=rss",
    "SCMP": "https://www.scmp.com/rss/91/feed",
}

DEFAULT_MAJOR_KEYWORDS = [
    "breaking",
    "urgent",
    "election",
    "war",
    "ceasefire",
    "attack",
    "missile",
    "killed",
    "dead",
    "explosion",
    "earthquake",
    "flood",
    "hurricane",
    "wildfire",
    "sanction",
    "supreme court",
    "white house",
    "fed",
    "interest rate",
    "inflation",
    "recession",
    "bankruptcy",
    "merger",
    "acquisition",
    "ipo",
    "earnings",
    "tariff",
    "taiwan",
    "south china sea",
    # User-focused topics
    "trump",
    "xi jinping",
    "习近平",
    "巴以冲突",
    "israel",
    "israeli",
    "palestine",
    "palestinian",
    "gaza",
    "hamas",
    "west bank",
    "俄乌战争",
    "ukraine",
    "ukrainian",
    "russia",
    "russian",
    "putin",
    "zelensky",
    "kyiv",
    "moscow",
    "乌克兰",
    "俄罗斯",
    "eu",
    "europe",
    "european",
    "eurozone",
    "ecb",
    "brussels",
    "africa",
    "african",
    "非洲",
    "sudan",
    "darfur",
    "congo",
    "drc",
    "somalia",
    "sahel",
    "boko haram",
    "al-shabaab",
    "greenland",
    "格陵兰",
    "格陵兰岛",
    "southeast asia",
    "asean",
    "东南亚",
    "philippines",
    "vietnam",
    "thailand",
    "myanmar",
    "indonesia",
    "malaysia",
    "singapore",
    "cambodia",
    "laos",
]

DEFAULT_FALLBACK_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/512px-No_image_available.svg.png"

SUMMARY_MAX_HEADLINES = 16
SUMMARY_MAX_LINKS = 16


def resolve_news_timezone() -> tuple[str, tzinfo]:
    tz_name = (os.getenv("NEWS_TZ") or os.getenv("TZ") or "").strip()
    if tz_name:
        try:
            return tz_name, ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logging.warning("未知时区: %s，将回退到UTC", tz_name)
        except Exception:
            logging.exception("解析时区失败: %s，将回退到UTC", tz_name)
    return "UTC", timezone.utc


def source_logo_url(source: str) -> str:
    domain = SOURCE_DOMAINS.get(source, "")
    if not domain:
        return ""
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=256"


def source_logo_candidates(source: str) -> List[str]:
    domain = SOURCE_DOMAINS.get(source, "")
    if not domain:
        return []
    return [
        f"https://logo.clearbit.com/{domain}",
        source_logo_url(source),
    ]


def extract_image_from_html(page_url: str, html_text: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if not match:
            continue
        url = html.unescape(match.group(1)).strip()
        if not url:
            continue
        return urllib.parse.urljoin(page_url, url)
    return ""


def fetch_article_image(article_url: str, timeout: int = 20) -> str:
    if not article_url:
        return ""
    req = urllib.request.Request(
        article_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl() or article_url
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return ""
        content = resp.read(700_000)
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return extract_image_from_html(final_url, text)


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


def google_news_rss_url(domain: str) -> str:
    q = urllib.parse.quote_plus(f"site:{domain}")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def build_source_feeds() -> Dict[str, str]:
    out = dict(SOURCE_FEEDS)
    for name, domain in SOURCE_DOMAINS.items():
        out.setdefault(name, google_news_rss_url(domain))
    return out


def now_ts() -> int:
    return int(time.time())


def load_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {"initialized": False, "seen": {}, "night_buffer": [], "last_digest_date": ""}
    try:
        with state_file.open("r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        logging.exception("读取状态文件失败，使用空状态")
        return {"initialized": False, "seen": {}, "night_buffer": [], "last_digest_date": ""}

    if not isinstance(state, dict):
        state = {}
    state.setdefault("initialized", False)
    state.setdefault("seen", {})
    state.setdefault("night_buffer", [])
    state.setdefault("last_digest_date", "")
    state.setdefault("last_run", {})
    if not isinstance(state.get("last_run"), dict):
        state["last_run"] = {}
    return state


def try_git(args: List[str]) -> str:
    try:
        return subprocess.check_output(args, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def github_run_url() -> str:
    server = (os.getenv("GITHUB_SERVER_URL") or "").strip()
    repo = (os.getenv("GITHUB_REPOSITORY") or "").strip()
    run_id = (os.getenv("GITHUB_RUN_ID") or "").strip()
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def save_state(state_file: Path, state: dict) -> None:
    tmp_file = state_file.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp_file.replace(state_file)


def prune_seen(seen: dict, ttl_hours: int) -> dict:
    cutoff = now_ts() - ttl_hours * 3600
    return {k: v for k, v in seen.items() if isinstance(v, int) and v >= cutoff}


def http_get_bytes(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def text_or_empty(elem: ET.Element, child_name: str) -> str:
    for child in list(elem):
        if local_name(child.tag).lower() == child_name.lower():
            return (child.text or "").strip()
    return ""


def rss_item_image_url(item: ET.Element) -> str:
    for child in list(item):
        name = local_name(child.tag).lower()
        if name == "image":
            url = (child.text or "").strip()
            if url:
                return url
        if name in ("content", "thumbnail"):
            url = (child.attrib.get("url") or "").strip()
            if url:
                return url
        if name == "enclosure":
            type_value = (child.attrib.get("type") or "").lower()
            url = (child.attrib.get("url") or "").strip()
            if url and type_value.startswith("image"):
                return url
    return ""


def parse_rss_items(root: ET.Element) -> List[dict]:
    out = []
    for item in root.iter():
        if local_name(item.tag).lower() != "item":
            continue
        title = text_or_empty(item, "title")
        link = normalize_news_link(text_or_empty(item, "link"))
        published = text_or_empty(item, "pubDate") or text_or_empty(item, "published")
        guid = text_or_empty(item, "guid")
        image_url = normalize_image_url(rss_item_image_url(item))
        out.append(
            {
                "id": guid or link or title,
                "title": title,
                "link": link,
                "published": published,
                "image_url": image_url,
            }
        )
    return out


def normalize_news_link(link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""
    try:
        u = urllib.parse.urlparse(link)
        host = (u.netloc or "").lower()
        if host.endswith("bing.com") and u.path.startswith("/news/apiclick.aspx"):
            q = urllib.parse.parse_qs(u.query)
            raw = (q.get("url") or [""])[0]
            if raw:
                return urllib.parse.unquote(raw)
    except Exception:
        return link
    return link


def normalize_image_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]

    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.netloc or "").lower()

        # Bing News default thumbnail is often 100x100; request high-res frame.
        if host.endswith("bing.com") and parsed.path == "/th":
            q = urllib.parse.parse_qs(parsed.query)
            if q.get("id") or q.get("thid"):
                q["w"] = ["1600"]
                q["h"] = ["900"]
                q["c"] = ["14"]
                q["rs"] = ["1"]
                new_query = urllib.parse.urlencode(q, doseq=True)
                return urllib.parse.urlunparse(parsed._replace(query=new_query))

        # Google-hosted images often include width parameters like '=s0-w300-rw'.
        if host.endswith("googleusercontent.com"):
            url = re.sub(r"=s0-w\\d+(-rw)?", "=s0-w1600-rw", url)
            url = re.sub(r"=w\\d+-h\\d+(-p)?", "=w1600-h900-p", url)
            return url
    except Exception:
        return url

    return url


def parse_atom_entries(root: ET.Element) -> List[dict]:
    out = []
    for entry in root.iter():
        if local_name(entry.tag).lower() != "entry":
            continue

        title = text_or_empty(entry, "title")
        published = text_or_empty(entry, "published") or text_or_empty(entry, "updated")
        uid = text_or_empty(entry, "id")

        link = ""
        image_url = ""
        for child in list(entry):
            if local_name(child.tag).lower() == "link":
                href = (child.attrib.get("href") or "").strip()
                rel = (child.attrib.get("rel") or "alternate").strip().lower()
                type_value = (child.attrib.get("type") or "").lower()
                if href and rel == "alternate":
                    link = href
                if href and rel == "enclosure" and type_value.startswith("image"):
                    image_url = normalize_image_url(href)

        out.append(
            {
                "id": uid or link or title,
                "title": title,
                "link": link,
                "published": published,
                "image_url": image_url,
            }
        )
    return out


def fetch_entries(url: str) -> List[dict]:
    data = http_get_bytes(url)
    root = ET.fromstring(data)
    root_name = local_name(root.tag).lower()

    if root_name == "rss":
        return parse_rss_items(root)
    if root_name == "feed":
        return parse_atom_entries(root)

    entries = parse_rss_items(root)
    if entries:
        return entries
    return parse_atom_entries(root)


def entry_uid(entry: dict) -> str:
    uid = entry.get("id") or entry.get("link") or entry.get("title")
    return str(uid).strip()


def entry_time_text(entry: dict) -> str:
    if entry.get("published"):
        return str(entry.get("published"))
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def parse_keywords(raw: str) -> List[str]:
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def build_keyword_patterns(keywords: List[str]) -> List[re.Pattern]:
    patterns = []
    for kw in keywords:
        kw = (kw or "").strip()
        if not kw:
            continue

        is_ascii = kw.isascii()
        if is_ascii:
            # For ASCII keywords:
            # - Match full words / phrases (avoid matching inside other words: fed != federal).
            # - Allow hyphen in multi-word phrases (e.g. "White-House").
            part = r"[\s\-]+".join(re.escape(p) for p in kw.split())
            patterns.append(
                re.compile(r"(?<![A-Za-z0-9_])" + part + r"(?![A-Za-z0-9_])", re.IGNORECASE)
            )
        else:
            # For non-ASCII (e.g. CJK), \b word boundary is unreliable (titles often have no spaces).
            # Use substring match instead.
            patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
    return patterns


def is_major_news(entry: dict, keyword_patterns: List[re.Pattern]) -> bool:
    title = (entry.get("title") or "").strip()
    lower_title = title.lower()
    if "opinion" in lower_title:
        return False
    return any(p.search(title) for p in keyword_patterns)


def is_quiet_time(now_local: datetime, quiet_start: int, quiet_end: int) -> bool:
    h = now_local.hour
    if quiet_start < quiet_end:
        return quiet_start <= h < quiet_end
    return h >= quiet_start or h < quiet_end


def build_caption(source: str, entry: dict, prefix: str = "") -> str:
    title = (entry.get("title") or "(无标题)").strip()
    link = (entry.get("link") or "").strip()
    published = entry_time_text(entry)
    text = f"{prefix}[{source}]\n{title}\n{published}\n{link}".strip()
    return text[:1024]


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
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API 返回失败: {data}")
    return data


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    telegram_api_json(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
        },
    )


def send_telegram_photo(token: str, chat_id: str, photo_url: str, caption: str) -> None:
    telegram_api_json(
        token,
        "sendPhoto",
        {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
        },
    )


def send_news_item(
    token: str, chat_id: str, source: str, entry: dict, prefix: str = "", fetch_article_image_enabled: bool = True
) -> None:
    caption = build_caption(source, entry, prefix=prefix)
    article_image = ""
    if fetch_article_image_enabled:
        try:
            article_image = normalize_image_url(fetch_article_image((entry.get("link") or "").strip()))
        except Exception:
            logging.exception("抓取正文配图失败，source=%s", source)

    image_candidates = [normalize_image_url((entry.get("image_url") or "").strip()), article_image]
    image_candidates.extend(normalize_image_url(x) for x in source_logo_candidates(source))
    image_candidates.append(DEFAULT_FALLBACK_IMAGE)
    tried = set()
    for image_url in image_candidates:
        if not image_url or image_url in tried:
            continue
        tried.add(image_url)
        try:
            send_telegram_photo(token, chat_id, image_url, caption)
            return
        except Exception:
            logging.exception("sendPhoto失败，source=%s url=%s", source, image_url)
    # Fallback: photos can fail due to Telegram not being able to fetch the remote image.
    # In that case, still send the text so news isn't silently lost.
    try:
        send_telegram_message(token, chat_id, caption)
        logging.info("sendPhoto均失败，已降级为sendMessage，source=%s", source)
        return
    except Exception as exc:
        raise RuntimeError("所有可用图片URL都发送失败且sendMessage也失败") from exc


def build_rule_summary_text(items: List[dict], tz_name: str, now_local: datetime) -> str:
    source_counts: Dict[str, int] = {}
    for it in items:
        src = it.get("source") or "未知来源"
        source_counts[src] = source_counts.get(src, 0) + 1
    top_sources = ", ".join(f"{k}:{v}" for k, v in sorted(source_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]) or "未知"
    lines = [
        f"【新闻汇总】本轮共 {len(items)} 条（{now_local.strftime('%Y-%m-%d %H:%M')} {tz_name}）",
        f"主要来源：{top_sources}",
        "",
        "标题速览：",
    ]
    headline_items = items[:SUMMARY_MAX_HEADLINES]
    for idx, item in enumerate(headline_items, start=1):
        source = item.get("source") or "未知来源"
        entry = item.get("entry") or {}
        title = (entry.get("title") or "(无标题)").strip().replace("\n", " ")
        if len(title) > 92:
            title = title[:89] + "..."
        lines.append(f"{idx}. [{source}] {title}")

    links = []
    for idx, item in enumerate(items[:SUMMARY_MAX_LINKS], start=1):
        link = ((item.get("entry") or {}).get("link") or "").strip()
        if link:
            links.append(f"{idx}) {link}")

    if links:
        lines.extend(["", "链接索引（点开看详情）：", *links])

    text = "\n".join(lines)
    return text[:3900]


def build_ai_summary_text(
    items: List[dict], tz_name: str, now_local: datetime, api_key: str, model: str, max_items: int = 30
) -> str:
    focus = items[: max(1, max_items)]
    events = []
    for idx, item in enumerate(focus, start=1):
        source = item.get("source") or "未知来源"
        entry = item.get("entry") or {}
        title = (entry.get("title") or "(无标题)").strip().replace("\n", " ")
        link = (entry.get("link") or "").strip()
        events.append(f"{idx}. [{source}] {title}\n链接: {link}")

    system_msg = (
        "你是新闻编辑。请输出高信息密度摘要，目标是在一条消息里看到尽量多标题并能点链接。"
        "输出格式："
        "1) 先给1行总体概览；"
        "2) 给“标题速览”清单（至少10条，格式：序号.[来源] 标题）；"
        "3) 给“链接索引”（序号对应URL）；"
        "4) 不要编造。"
    )
    user_msg = (
        f"时间: {now_local.strftime('%Y-%m-%d %H:%M')} {tz_name}\n"
        f"新闻共 {len(items)} 条，以下是前 {len(focus)} 条:\n\n" + "\n\n".join(events)
    )

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    text = (text or "").strip()
    if not text:
        raise RuntimeError(f"AI总结返回为空: {data}")
    return f"【AI新闻汇总】{now_local.strftime('%m-%d %H:%M')} {tz_name}\n{text}"[:3900]


def maybe_send_compact_summary(
    token: str,
    chat_id: str,
    items: List[dict],
    tz_name: str,
    now_local: datetime,
    threshold: int,
    ai_api_key: str,
    ai_model: str,
    ai_max_items: int,
) -> bool:
    if len(items) <= threshold:
        return False

    summary_text = ""
    if ai_api_key:
        try:
            summary_text = build_ai_summary_text(
                items=items,
                tz_name=tz_name,
                now_local=now_local,
                api_key=ai_api_key,
                model=ai_model,
                max_items=ai_max_items,
            )
            logging.info("AI汇总成功，条数=%s model=%s", len(items), ai_model)
        except Exception:
            logging.exception("AI汇总失败，将降级为规则汇总")

    if not summary_text:
        summary_text = build_rule_summary_text(items=items, tz_name=tz_name, now_local=now_local)

    top_links = []
    for item in items[:SUMMARY_MAX_LINKS]:
        entry = item.get("entry") or {}
        link = (entry.get("link") or "").strip()
        if link:
            top_links.append(link)
    if top_links and ("链接索引" not in summary_text):
        summary_text = f"{summary_text}\n\n参考链接:\n" + "\n".join(f"- {x}" for x in top_links)

    send_telegram_message(token, chat_id, summary_text[:3900])
    return True


def flush_night_digest(
    token: str,
    chat_id: str,
    state: dict,
    today_str: str,
    now_local: datetime,
    tz_name: str,
    summary_threshold: int,
    ai_api_key: str,
    ai_model: str,
    ai_max_items: int,
    fetch_article_image_enabled: bool = True,
) -> None:
    buffered = state.get("night_buffer", [])
    if not buffered:
        return

    logging.info("发送夜间汇总，条数=%s", len(buffered))
    if maybe_send_compact_summary(
        token=token,
        chat_id=chat_id,
        items=buffered,
        tz_name=tz_name,
        now_local=now_local,
        threshold=summary_threshold,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
        ai_max_items=ai_max_items,
    ):
        state["night_buffer"] = []
        state["last_digest_date"] = today_str
        logging.info("夜间缓存已汇总推送，条数=%s", len(buffered))
        return

    remain = []
    ok = 0
    failed = 0
    for item in buffered:
        source = item.get("source") or "未知来源"
        entry = item.get("entry") or {}
        try:
            send_news_item(
                token,
                chat_id,
                source,
                entry,
                prefix="[夜间汇总] ",
                fetch_article_image_enabled=fetch_article_image_enabled,
            )
            ok += 1
        except Exception:
            failed += 1
            remain.append(item)
            logging.exception("夜间汇总推送失败: %s", source)

    if failed:
        # Keep failed items for retry on next cycle (don't set last_digest_date).
        state["night_buffer"] = remain
        logging.warning("夜间汇总部分失败，成功=%s 失败=%s，将在下轮重试失败项", ok, failed)
        return

    state["night_buffer"] = []
    state["last_digest_date"] = today_str


def run(run_once: bool = False) -> None:
    load_dotenv_simple()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    poll_seconds = int(os.getenv("POLL_SECONDS", "120"))
    max_items_per_source = int(os.getenv("MAX_ITEMS_PER_SOURCE", "3"))
    bootstrap_silent = os.getenv("BOOTSTRAP_SILENT", "true").strip().lower() == "true"
    state_file = Path(os.getenv("STATE_FILE", ".state.json"))
    seen_ttl_hours = int(os.getenv("SEEN_TTL_HOURS", "72"))
    major_only = os.getenv("MAJOR_ONLY", "true").strip().lower() == "true"
    major_keywords = parse_keywords(os.getenv("MAJOR_KEYWORDS", ",".join(DEFAULT_MAJOR_KEYWORDS)))
    keyword_patterns = build_keyword_patterns(major_keywords)
    quiet_start = int(os.getenv("QUIET_HOUR_START", "23"))
    quiet_end = int(os.getenv("QUIET_HOUR_END", "9"))
    night_digest_max = int(os.getenv("NIGHT_DIGEST_MAX", "40"))
    fetch_article_image_enabled = os.getenv("FETCH_ARTICLE_IMAGE", "true").strip().lower() == "true"
    ai_summary_threshold = int(os.getenv("AI_SUMMARY_THRESHOLD", "10"))
    ai_summary_model = (os.getenv("AI_SUMMARY_MODEL", "gpt-5-mini") or "gpt-5-mini").strip()
    ai_summary_max_items = int(os.getenv("AI_SUMMARY_MAX_ITEMS", "30"))
    openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    tz_name, news_tz = resolve_news_timezone()

    if not token or not chat_id:
        raise RuntimeError("请先配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")

    source_feeds = build_source_feeds()
    state = load_state(state_file)
    state["seen"] = prune_seen(state.get("seen", {}), seen_ttl_hours)

    logging.info(
        "开始运行，轮询间隔=%s秒，来源数量=%s，时区=%s quiet=%02d-%02d",
        poll_seconds,
        len(source_feeds),
        tz_name,
        quiet_start,
        quiet_end,
    )

    while True:
        try:
            now_local = datetime.now(tz=news_tz)
            cycle_ts = now_ts()
            today_str = now_local.strftime("%Y-%m-%d")
            quiet_now = is_quiet_time(now_local, quiet_start, quiet_end)

            if (not quiet_now) and now_local.hour >= quiet_end and state.get("last_digest_date", "") != today_str:
                flush_night_digest(
                    token=token,
                    chat_id=chat_id,
                    state=state,
                    today_str=today_str,
                    now_local=now_local,
                    tz_name=tz_name,
                    summary_threshold=ai_summary_threshold,
                    ai_api_key=openai_api_key,
                    ai_model=ai_summary_model,
                    ai_max_items=ai_summary_max_items,
                    fetch_article_image_enabled=fetch_article_image_enabled,
                )

            sources_ok = 0
            sources_fail = 0
            entries_total = 0
            skipped_seen = 0
            skipped_major = 0
            pushed_ok = 0
            pushed_fail = 0
            buffered_added = 0
            all_new = []
            cycle_seen = set()
            for source, url in source_feeds.items():
                try:
                    entries = fetch_entries(url)
                except Exception:
                    sources_fail += 1
                    logging.exception("抓取失败: %s", source)
                    continue
                sources_ok += 1
                entries_total += len(entries)

                new_count = 0
                for entry in entries:
                    uid = entry_uid(entry)
                    if not uid:
                        continue
                    if uid in state["seen"] or uid in cycle_seen:
                        if uid in state["seen"]:
                            skipped_seen += 1
                        continue

                    if major_only and (not is_major_news(entry, keyword_patterns)):
                        skipped_major += 1
                        continue

                    cycle_seen.add(uid)
                    all_new.append((source, entry, uid))
                    new_count += 1
                    if new_count >= max_items_per_source:
                        break

            state["seen"] = prune_seen(state["seen"], seen_ttl_hours)

            if sources_ok == 0:
                logging.warning("本轮所有来源抓取均失败（sources_fail=%s），可能是网络/被封/源站变更导致", sources_fail)
            if entries_total > 0 and len(all_new) == 0:
                if major_only and skipped_major > 0:
                    logging.info(
                        "本轮有内容但未命中关键词：entries_total=%s skipped_major=%s skipped_seen=%s",
                        entries_total,
                        skipped_major,
                        skipped_seen,
                    )
                else:
                    logging.info(
                        "本轮有内容但没有新条目：entries_total=%s skipped_seen=%s",
                        entries_total,
                        skipped_seen,
                    )

            if not state.get("initialized", False):
                # Seed seen cache on the very first run (prevents historical spam).
                for _source, _entry, uid in all_new:
                    state["seen"][uid] = cycle_ts
                state["initialized"] = True
                save_state(state_file, state)
                if bootstrap_silent:
                    logging.info("首次启动完成，已建立去重缓存（静默模式）")
                    if run_once:
                        break
                    time.sleep(poll_seconds)
                    continue

            if quiet_now:
                buffered = state.get("night_buffer", [])
                for source, entry, uid in all_new:
                    if len(buffered) >= night_digest_max:
                        break
                    buffered.append({"source": source, "entry": entry})
                    state["seen"][uid] = cycle_ts
                    buffered_added += 1
                state["night_buffer"] = buffered
                if buffered_added:
                    logging.info("夜间免打扰生效，新增%s条进入汇总缓存", buffered_added)
            else:
                compact_items = [{"source": s, "entry": e, "uid": u} for s, e, u in all_new]
                sent_compact = False
                try:
                    sent_compact = maybe_send_compact_summary(
                        token=token,
                        chat_id=chat_id,
                        items=compact_items,
                        tz_name=tz_name,
                        now_local=now_local,
                        threshold=ai_summary_threshold,
                        ai_api_key=openai_api_key,
                        ai_model=ai_summary_model,
                        ai_max_items=ai_summary_max_items,
                    )
                except Exception:
                    logging.exception("汇总推送失败，将回退逐条发送")
                    sent_compact = False

                if sent_compact:
                    for _source, _entry, uid in all_new:
                        state["seen"][uid] = cycle_ts
                    pushed_ok += 1
                    logging.info("已推送汇总消息，覆盖条数=%s", len(all_new))
                else:
                    for source, entry, uid in all_new:
                        try:
                            send_news_item(
                                token, chat_id, source, entry, fetch_article_image_enabled=fetch_article_image_enabled
                            )
                            state["seen"][uid] = cycle_ts
                            pushed_ok += 1
                            logging.info("已推送: %s | %s", source, entry.get("title", ""))
                        except Exception:
                            pushed_fail += 1
                            logging.exception("推送失败: %s", source)

            checkout_sha = try_git(["git", "rev-parse", "HEAD"])
            checkout_ref = try_git(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            if checkout_ref == "HEAD":
                checkout_ref = ""

            utc_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            state["last_run"] = {
                "utc": utc_now,
                "local": now_local.replace(microsecond=0).isoformat(),
                "tz": tz_name,
                "local_hour": now_local.hour,
                "quiet": quiet_now,
                "sources_ok": sources_ok,
                "sources_fail": sources_fail,
                "entries_total": entries_total,
                "new": len(all_new),
                "pushed_ok": pushed_ok,
                "pushed_fail": pushed_fail,
                "skipped_seen": skipped_seen,
                "skipped_major": skipped_major,
                "buffered_total": len(state.get("night_buffer", [])),
                "buffered_added": buffered_added,
                "seen_size": len(state.get("seen", {})) if isinstance(state.get("seen"), dict) else 0,
                "github": {
                    "repo": (os.getenv("GITHUB_REPOSITORY") or "").strip(),
                    "workflow": (os.getenv("GITHUB_WORKFLOW") or "").strip(),
                    "run_id": (os.getenv("GITHUB_RUN_ID") or "").strip(),
                    "run_number": (os.getenv("GITHUB_RUN_NUMBER") or "").strip(),
                    "sha": (os.getenv("GITHUB_SHA") or "").strip(),
                    "ref": (os.getenv("GITHUB_REF") or "").strip(),
                    "run_url": github_run_url(),
                },
                "checkout": {
                    "ref": checkout_ref,
                    "sha": checkout_sha,
                },
            }

            save_state(state_file, state)
            logging.info(
                "summary tz=%s local_hour=%s quiet=%s sources_ok=%s sources_fail=%s entries_total=%s new=%s pushed_ok=%s pushed_fail=%s skipped_seen=%s skipped_major=%s buffered=%s buffered_added=%s",
                tz_name,
                now_local.hour,
                quiet_now,
                sources_ok,
                sources_fail,
                entries_total,
                len(all_new),
                pushed_ok,
                pushed_fail,
                skipped_seen,
                skipped_major,
                len(state.get("night_buffer", [])),
                buffered_added,
            )
            logging.info("本轮完成，新消息=%s", len(all_new))
        except Exception:
            logging.exception("主循环异常")

        if run_once:
            break
        time.sleep(poll_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram News Notifier")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run(run_once=args.once)
