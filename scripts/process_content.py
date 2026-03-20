from __future__ import annotations

import os
from datetime import date
from typing import List, Dict, Any

from openai import OpenAI
from common import load_json, dump_json, load_yaml


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for x in items:
        key = (x.get("title") or x.get("name"), x.get("url"))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def ai_generate(prompt: str, fallback: str, max_len: int = 40) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个资深科技媒体编辑"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()
        result = " ".join(result.split())
        return result[:max_len]

    except Exception as e:
        print(f"[WARN] AI失败: {e}")
        return fallback[:max_len]


def simplify_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return ""

    prompt = f"""请把下面这条标题改写成简短中文新闻标题（15字以内）：

{title}
"""
    return ai_generate(prompt, title, 20)


def simplify_summary(summary: str) -> str:
    summary = (summary or "").strip()
    if not summary:
        return ""

    prompt = f"""请把下面内容改写成30字以内中文摘要：

{summary}
"""
    return ai_generate(prompt, summary, 40)


def score_item(item: Dict[str, Any], bucket: str, source_priority: Dict[str, int], keyword_conf: Dict[str, Any]) -> int:
    title = (item.get("title") or item.get("name") or "").lower()
    source = item.get("source", "")
    score = 0

    # 来源优先级
    score += source_priority.get(source, 0) * 10

    # 关键词优先级
    bucket_keywords = keyword_conf.get(bucket, {})
    high_keywords = bucket_keywords.get("high", [])
    medium_keywords = bucket_keywords.get("medium", [])

    for kw in high_keywords:
        if kw.lower() in title:
            score += 30

    for kw in medium_keywords:
        if kw.lower() in title:
            score += 10

    # 轻度惩罚：太长太泛的标题
    if len(title) > 120:
        score -= 5

    return score


def build_source_priority(source_list: List[Dict[str, Any]]) -> Dict[str, int]:
    result = {}
    for s in source_list:
        result[s["name"]] = s.get("priority", 0)
    return result


def main():
    news = load_json("data/raw/news.json", {})
    products = load_json("data/raw/products.json", {"products": []})
    festivals = load_json(
        "data/processed/festivals.json",
        {"festival_cards": [], "festival_pages": []}
    )
    config = load_yaml("config/news_sources.yaml")

    consumer = dedupe(news.get("consumer_electronics", []))
    channel = dedupe(news.get("channel_news", []))

    consumer_source_priority = build_source_priority(
        config["sources"].get("consumer_electronics", [])
    )
    channel_source_priority = build_source_priority(
        config["sources"].get("channel_news", [])
    )
    keyword_conf = config.get("keywords", {})

    # 打分排序：今日热点
    for x in consumer:
        x["_score"] = score_item(
            x,
            "consumer_electronics",
            consumer_source_priority,
            keyword_conf
        )
        x["display_title"] = simplify_title(x.get("title", ""))

    consumer = sorted(consumer, key=lambda x: x["_score"], reverse=True)[:9]

    # 打分排序：渠道新闻
    for x in channel:
        x["_score"] = score_item(
            x,
            "channel_news",
            channel_source_priority,
            keyword_conf
        )
        x["display_title"] = simplify_title(x.get("title", ""))

    channel = sorted(channel, key=lambda x: x["_score"], reverse=True)[:9]

    # 新品速递
    product_items = dedupe(products.get("products", []))[:6]

    for x in product_items:
        name = x.get("name", "")
        summary = x.get("summary", "")
        x["display_title"] = simplify_title(name) or name
        x["display_summary"] = simplify_summary(summary) or summary

    payload = {
        "date": str(date.today()),
        "festival_cards": festivals.get("festival_cards", []),
        "festival_pages": festivals.get("festival_pages", []),
        "consumer_electronics": consumer,
        "channel_news": channel,
        "products": product_items,
    }

    dump_json("data/processed/daily_payload.json", payload)
    print("[OK] payload generated")


if __name__ == "__main__":
    main()
