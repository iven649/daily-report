from __future__ import annotations

import time
from typing import Dict, List

import feedparser

from common import (
    build_dedupe_key,
    dump_json,
    is_meaningful_text,
    load_yaml,
    logger,
    parse_datetime,
)

MAX_PER_SOURCE = 12


def clean_text(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    return " ".join(text.split())


def fetch_rss(url: str) -> List[Dict]:
    feed = feedparser.parse(url)
    items = []

    for e in feed.entries[:MAX_PER_SOURCE]:
        title = clean_text(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        published = clean_text(getattr(e, "published", ""))
        summary = clean_text(getattr(e, "summary", "") or getattr(e, "description", ""))

        if not is_meaningful_text(title, 6):
            continue
        if not link:
            continue

        published_dt = parse_datetime(published)

        items.append(
            {
                "title": title,
                "summary": summary[:320],
                "url": link,
                "published": published,
                "published_iso": published_dt.isoformat() if published_dt else "",
            }
        )

    return items


def dedupe_news_items(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []

    for item in items:
        key = build_dedupe_key(
            title=item.get("title", ""),
            url=item.get("url", ""),
            summary=item.get("summary", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out


def main() -> None:
    conf = load_yaml("config/news_sources.yaml")
    result = {
        "consumer_electronics": [],
        "channel_news": [],
        "fetched_at": int(time.time()),
    }

    for bucket in ("consumer_electronics", "channel_news"):
        sources = conf.get("sources", {}).get(bucket, [])
        logger.info(f"Fetching news bucket={bucket}, sources={len(sources)}")

        bucket_items = []

        for source in sources:
            if source.get("type") != "rss":
                logger.warning(
                    f"Skip unsupported source type: {source.get('name')} ({source.get('type')})"
                )
                continue

            try:
                items = fetch_rss(source["url"])
                for x in items:
                    x["source"] = source["name"]
                    x["bucket"] = bucket
                bucket_items.extend(items)
                logger.info(f"Fetched {len(items)} items from {source['name']}")
            except Exception as e:
                logger.warning(f"News source failed: {source['name']} -> {e}")

        deduped = dedupe_news_items(bucket_items)
        logger.info(f"Bucket {bucket} raw={len(bucket_items)} deduped={len(deduped)}")
        result[bucket] = deduped

    total = len(result["consumer_electronics"]) + len(result["channel_news"])
    dump_json("data/raw/news.json", result)
    logger.info(
        f"Saved data/raw/news.json | consumer={len(result['consumer_electronics'])}, "
        f"channel={len(result['channel_news'])}, total={total}"
    )


if __name__ == "__main__":
    main()
