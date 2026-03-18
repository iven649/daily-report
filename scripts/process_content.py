from __future__ import annotations
from datetime import date
from common import load_json, dump_json

def dedupe(items):
    seen = set()
    out = []
    for x in items:
        key = (x.get("title") or x.get("name"), x.get("url"))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out

def simplify_title(title: str) -> str:
    title = (title or "").strip()
    return " ".join(title.split())[:80]

def main():
    news = load_json("data/raw/news.json", {})
    products = load_json("data/raw/products.json", {"products": []})
    festivals = load_json("data/processed/festivals.json", {"festival_cards": [], "festival_pages": []})

    consumer = dedupe(news.get("consumer_electronics", []))[:9]
    channel = dedupe(news.get("channel_news", []))[:9]

    for bucket in (consumer, channel):
        for x in bucket:
            x["display_title"] = simplify_title(x.get("title", ""))

    product_items = dedupe(products.get("products", []))[:6]

    payload = {
        "date": str(date.today()),
        "festival_cards": festivals.get("festival_cards", []),
        "festival_pages": festivals.get("festival_pages", []),
        "consumer_electronics": consumer,
        "channel_news": channel,
        "products": product_items,
    }
    dump_json("data/processed/daily_payload.json", payload)
    print("[OK] data/processed/daily_payload.json")

if __name__ == "__main__":
    main()
