from __future__ import annotations

import time
from typing import Any, Dict, List

import feedparser

from common import (
    build_dedupe_key,
    dump_json,
    is_meaningful_text,
    load_yaml,
    logger,
    parse_datetime,
)


def normalize(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split()).strip()


def score_product_item(
    item: Dict[str, Any],
    source_priority: Dict[str, int],
    keyword_conf: Dict[str, Any],
) -> int:
    title = (item.get("name") or "").lower()
    summary = (item.get("summary") or "").lower()
    source = item.get("source", "")
    text = f"{title} {summary}"

    score = 0
    score += source_priority.get(source, 0) * 10

    trigger_keywords = keyword_conf.get("trigger", [])
    trigger_hits = sum(1 for kw in trigger_keywords if kw.lower() in text)
    score += trigger_hits * 12

    high_keywords = keyword_conf.get("high", [])
    high_hits = sum(1 for kw in high_keywords if kw.lower() in text)
    score += high_hits * 18

    medium_keywords = keyword_conf.get("medium", [])
    medium_hits = sum(1 for kw in medium_keywords if kw.lower() in text)
    score += medium_hits * 8

    if "open-ear" in text or "open ear" in text:
        score += 24
    if "bone conduction" in text:
        score += 24
    if "sports headphones" in text:
        score += 18

    if trigger_hits == 0 and high_hits == 0 and medium_hits == 0:
        score -= 80

    if len(title) > 140:
        score -= 5

    return score


def build_source_priority(source_list: List[Dict[str, Any]]) -> Dict[str, int]:
    return {s["name"]: s.get("priority", 0) for s in source_list}


def fetch_rss(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    parsed = feedparser.parse(source["url"])
    items = []

    for entry in parsed.entries[:24]:
        title = normalize(getattr(entry, "title", ""))
        summary = normalize(getattr(entry, "summary", ""))
        link = getattr(entry, "link", "")
        published = normalize(getattr(entry, "published", ""))

        if not is_meaningful_text(title, 6):
            continue
        if not link:
            continue

        published_dt = parse_datetime(published)

        items.append(
            {
                "name": title,
                "summary": summary[:260],
                "date": published[:25],
                "published_iso": published_dt.isoformat() if published_dt else "",
                "url": link,
                "source": source["name"],
            }
        )

    return items


def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for x in items:
        key = build_dedupe_key(
            title=x.get("name", ""),
            url=x.get("url", ""),
            summary=x.get("summary", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(x)

    return out


def main() -> None:
    conf = load_yaml("config/product_sources.yaml")

    product_sources = conf["sources"].get("products", [])
    source_priority = build_source_priority(product_sources)
    keyword_conf = conf.get("keywords", {})

    products = []
    logger.info(f"Fetching product sources: {len(product_sources)}")

    for source in product_sources:
        try:
            items = fetch_rss(source)
            products.extend(items)
            logger.info(f"Fetched {len(items)} product items from {source['name']}")
        except Exception as e:
            logger.warning(f"Product source failed: {source['name']} -> {e}")

    raw_count = len(products)
    products = dedupe(products)

    for item in products:
        item["_score"] = score_product_item(item, source_priority, keyword_conf)

    products = [x for x in products if x["_score"] > 0]
    products.sort(key=lambda x: x["_score"], reverse=True)

    result = {
        "products": products[:12],
        "fetched_at": int(time.time()),
    }

    dump_json("data/raw/products.json", result)
    logger.info(
        f"Saved data/raw/products.json | raw={raw_count}, deduped={len(products)}, kept={len(result['products'])}"
    )


if __name__ == "__main__":
    main()
