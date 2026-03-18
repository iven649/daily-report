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


def simplify_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return ""

    try:
        prompt = f"""请把下面这条新闻或产品标题改写成简短自然的中文标题。

要求：
1. 12-18字优先，最多不超过20字
2. 像科技/商业媒体标题
3. 不要书名号，不要引号
4. 不要加解释，不要加前缀，不要换行
5. 只输出中文标题本身

原标题：
{title}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个资深科技媒体编辑，擅长把英文新闻标题改写成简洁自然的中文标题。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()
        result = " ".join(result.split())
        return result[:20]

    except Exception as e:
        print(f"[WARN] AI标题失败: {e}")
        return title[:40]


def simplify_summary(summary: str) -> str:
    summary = (summary or "").strip()
    if not summary:
        return ""

    try:
        prompt = f"""请把下面这段产品简介改写成简短自然的中文摘要。

要求：
1. 30字以内
2. 保留核心卖点
3. 像新品速递摘要
4. 不要解释，不要换行
5. 只输出中文摘要

原文：
{summary}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个科技媒体编辑，擅长把英文产品描述改写成简短自然的中文摘要。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip()
        result = " ".join(result.split())
        return result[:40]

    except Exception as e:
        print(f"[WARN] AI摘要失败: {e}")
        return summary[:80]


def main():
    news = load_json("data/raw/news.json", {})
    products = load_json("data/raw/products.json", {"products": []})
    festivals = load_json(
        "data/processed/festivals.json",
        {"festival_cards": [], "festival_pages": []}
    )

    consumer = dedupe(news.get("consumer_electronics", []))[:9]
    channel = dedupe(news.get("channel_news", []))[:9]

    for bucket in (consumer, channel):
        for x in bucket:
            x["display_title"] = simplify_title(x.get("title", ""))

    product_items = dedupe(products.get("products", []))[:6]
    for x in product_items:
        x["display_title"] = simplify_title(x.get("name", ""))
        x["display_summary"] = simplify_summary(x.get("summary", ""))

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
