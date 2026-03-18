from __future__ import annotations

import os
from datetime import date
from typing import List, Dict, Any

from openai import OpenAI
from common import load_json, dump_json


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


def main():
    news = load_json("data/raw/news.json", {})
    products = load_json("data/raw/products.json", {"products": []})
    festivals = load_json(
        "data/processed/festivals.json",
        {"festival_cards": [], "festival_pages": []}
    )

    consumer = dedupe(news.get("consumer_electronics", []))[:9]
    channel = dedupe(news.get("channel_news", []))[:9]

    # ✅ 新闻统一处理
    for bucket in (consumer, channel):
        for x in bucket:
            title = x.get("title", "")
            x["display_title"] = simplify_title(title)

    # ✅ 产品统一处理（关键修复点）
    product_items = dedupe(products.get("products", []))[:6]

    for x in product_items:
        name = x.get("name", "")
        summary = x.get("summary", "")

        # 强制保证字段存在
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
