from __future__ import annotations

import time
from typing import Dict, Any, List

import feedparser

from common import load_yaml, dump_json


def normalize(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split()).strip()


def score_product_item(item: Dict[str, Any], source_priority: Dict[str, int], keyword_conf: Dict[str, Any]) -> int:
    title = (item.get("name") or "").lower()
    summary = (item.get("summary") or "").lower()
    source = item.get("source", "")
    text = f"{title} {summary}"

    score = 0

    # 来源优先级
    score += source_priority.get(source, 0) * 10

    # 命中“发布类词”
    trigger_keywords = keyword_conf.get("trigger", [])
    trigger_hits = 0
    for kw in trigger_keywords:
        if kw.lower() in text:
            trigger_hits += 1
    score += trigger_hits * 12

    # 高优先关键词（耳机 / 音频 / 无人机 / 运动相机）
    high_keywords = keyword_conf.get("high", [])
    high_hits = 0
    for kw in high_keywords:
        if kw.lower() in text:
            high_hits += 1
    score += high_hits * 18

    # 中优先关键词（泛消费电子）
    medium_keywords = keyword_conf.get("medium", [])
    medium_hits = 0
    for kw in medium_keywords:
        if kw.lower() in text:
            medium_hits += 1
    score += medium_hits * 8

    # 强化你的优先级：耳机 > 无人机/运动相机 > 其他
    audio_keywords = [
        "headphones", "earbuds", "earbud", "headset", "speaker", "audio",
        "noise cancelling", "anc", "open-ear", "open ear", "bone conduction",
        "bose", "beats", "soundcore", "sony", "jbl", "sennheiser", "shokz"
    ]
    drone_camera_keywords = [
        "drone", "dji", "action camera", "gopro", "insta360", "osmo", "camera"
    ]

    audio_hits = sum(1 for kw in audio_keywords if kw in text)
    drone_hits = sum(1 for kw in drone_camera_keywords if kw in text)

    score += audio_hits * 25
    score += drone_hits * 16

    # 如果既没有发布词，也没有核心关键词，认为不是合格新品，强烈降权
    if trigger_hits == 0 and high_hits == 0 and medium_hits == 0:
        score -= 80

    # 太长太泛的内容轻微降权
    if len(title) > 140:
        score -= 5

    return score


def build_source_priority(source_list: List[Dict[str, Any]]) -> Dict[str, int]:
    result = {}
    for s in source_list:
        result[s["name"]] = s.get("priority", 0)
    return result


def fetch_rss(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    parsed = feedparser.parse(source["url"])
    items = []

    for entry in parsed.entries[:24]:
        title = normalize(getattr(entry, "title", ""))
        summary = normalize(getattr(entry, "summary", ""))
        link = getattr(entry, "link", "")
        published = getattr(entry, "published", "")

        items.append({
            "name": title,
            "summary": summary[:260],
            "date": published[:25],
            "url": link,
            "source": source["name"],
        })

    return items


def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for x in items:
        key = (x.get("name"), x.get("url"))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def main():
    conf = load_yaml("config/product_sources.yaml")

    product_sources = conf["sources"].get("products", [])
    source_priority = build_source_priority(product_sources)
    keyword_conf = conf.get("keywords", {})

    products = []

    for source in product_sources:
        try:
            items = fetch_rss(source)
            products.extend(items)
        except Exception as e:
            print(f"[WARN] product source failed: {source['name']} -> {e}")

    products = dedupe(products)

    for item in products:
        item["_score"] = score_product_item(item, source_priority, keyword_conf)

    # 只保留有意义的新品候选
    products = [x for x in products if x["_score"] > 0]

    # 按优先级排序
    products.sort(key=lambda x: x["_score"], reverse=True)

    # 最终输出前12条，供后续 process_content 再裁成 6 条
    result = {
        "products": products[:12],
        "fetched_at": int(time.time())
    }

    dump_json("data/raw/products.json", result)
    print("[OK] data/raw/products.json")


if __name__ == "__main__":
    main()
