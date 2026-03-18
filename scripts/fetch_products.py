from __future__ import annotations
import time
import feedparser
from common import load_yaml, dump_json

KEYWORDS = ["launch", "announce", "announced", "unveil", "unveils", "new", "debut", "release", "earbuds", "headphones", "phone", "laptop", "chip"]

def score(title: str) -> int:
    t = title.lower()
    return sum(1 for k in KEYWORDS if k in t)

def main():
    conf = load_yaml("config/product_sources.yaml")
    products = []

    for source in conf["sources"].get("products", []):
        try:
            feed = feedparser.parse(source["url"])
            for e in feed.entries[:20]:
                title = getattr(e, "title", "").strip()
                if score(title) < 1:
                    continue
                products.append({
                    "name": title[:70],
                    "summary": (getattr(e, "summary", "") or "").replace("<p>", "").replace("</p>", "")[:120],
                    "date": getattr(e, "published", "")[:16],
                    "url": getattr(e, "link", ""),
                    "source": source["name"],
                    "score": score(title),
                })
        except Exception as e:
            print(f"[WARN] product source failed: {source['name']} -> {e}")

    products.sort(key=lambda x: x["score"], reverse=True)
    dump_json("data/raw/products.json", {"products": products[:12], "fetched_at": int(time.time())})
    print("[OK] data/raw/products.json")

if __name__ == "__main__":
    main()
