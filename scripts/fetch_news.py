from __future__ import annotations
import time
import feedparser
from common import load_yaml, dump_json

MAX_PER_SOURCE = 12

def clean_title(title: str) -> str:
    title = (title or "").replace("\n", " ").strip()
    return " ".join(title.split())

def fetch_rss(url: str):
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:MAX_PER_SOURCE]:
        items.append({
            "title": clean_title(getattr(e, "title", "")),
            "url": getattr(e, "link", ""),
            "published": getattr(e, "published", ""),
        })
    return items

def main():
    conf = load_yaml("config/news_sources.yaml")
    result = {"consumer_electronics": [], "channel_news": [], "fetched_at": int(time.time())}

    for bucket in ("consumer_electronics", "channel_news"):
        for source in conf["sources"].get(bucket, []):
            if source["type"] != "rss":
                continue
            try:
                items = fetch_rss(source["url"])
                for x in items:
                    x["source"] = source["name"]
                    x["bucket"] = bucket
                result[bucket].extend(items)
            except Exception as e:
                print(f"[WARN] news source failed: {source['name']} -> {e}")

    dump_json("data/raw/news.json", result)
    print("[OK] data/raw/news.json")

if __name__ == "__main__":
    main()
