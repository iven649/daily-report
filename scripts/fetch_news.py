from __future__ import annotations

import time

import feedparser

from common import load_yaml, dump_json, logger

MAX_PER_SOURCE = 12


def clean_title(title: str) -> str:
    title = (title or "").replace("\n", " ").strip()
    return " ".join(title.split())


def fetch_rss(url: str):
    feed = feedparser.parse(url)
    items = []

    for e in feed.entries[:MAX_PER_SOURCE]:
        items.append(
            {
                "title": clean_title(getattr(e, "title", "")),
                "url": getattr(e, "link", ""),
                "published": getattr(e, "published", ""),
            }
        )

    return items


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
                result[bucket].extend(items)
                logger.info(f"Fetched {len(items)} items from {source['name']}")
            except Exception as e:
                logger.warning(f"News source failed: {source['name']} -> {e}")

    total = len(result["consumer_electronics"]) + len(result["channel_news"])
    dump_json("data/raw/news.json", result)
    logger.info(
        f"Saved data/raw/news.json | consumer={len(result['consumer_electronics'])}, "
        f"channel={len(result['channel_news'])}, total={total}"
    )


if __name__ == "__main__":
    main()
