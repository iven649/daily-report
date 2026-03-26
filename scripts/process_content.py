from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, List, Optional

from openai import OpenAI

from common import (
    build_dedupe_key,
    dump_json,
    is_meaningful_text,
    load_json,
    load_yaml,
    logger,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for x in items:
        title = x.get("title") or x.get("name", "")
        summary = x.get("summary", "")
        key = build_dedupe_key(title=title, url=x.get("url", ""), summary=summary)

        if key in seen:
            continue
        seen.add(key)
        out.append(x)

    return out


def filter_valid_items(items: List[Dict[str, Any]], title_field: str) -> List[Dict[str, Any]]:
    out = []
    for x in items:
        title = x.get(title_field, "")
        url = x.get("url", "")
        if not is_meaningful_text(title, 6):
            continue
        if not url:
            continue
        out.append(x)
    return out


def ai_generate(prompt: str, fallback: str, max_len: int = 40) -> str:
    if client is None:
        return fallback[:max_len]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个资深科技媒体编辑"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        result = (response.choices[0].message.content or "").strip()
        result = " ".join(result.split())
        return result[:max_len] if result else fallback[:max_len]

    except Exception as e:
        logger.warning(f"AI generate failed: {e}")
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


def score_item(
    item: Dict[str, Any],
    bucket: str,
    source_priority: Dict[str, int],
    keyword_conf: Dict[str, Any],
) -> int:
    title = (item.get("title") or item.get("name") or "").lower()
    summary = (item.get("summary") or "").lower()
    source = item.get("source", "")
    text = f"{title} {summary}"
    score = 0

    score += source_priority.get(source, 0) * 10

    bucket_keywords = keyword_conf.get(bucket, {})
    high_keywords = bucket_keywords.get("high", [])
    medium_keywords = bucket_keywords.get("medium", [])

    for kw in high_keywords:
        if kw.lower() in text:
            score += 30

    for kw in medium_keywords:
        if kw.lower() in text:
            score += 10

    if len(title) > 120:
        score -= 5

    return score


def build_source_priority(source_list: List[Dict[str, Any]]) -> Dict[str, int]:
    result = {}
    for s in source_list:
        result[s["name"]] = s.get("priority", 0)
    return result


def generate_takeaways(
    consumer_news: List[Dict[str, Any]],
    channel_news: List[Dict[str, Any]],
    products: List[Dict[str, Any]],
) -> List[str]:
    if not consumer_news and not channel_news and not products:
        return [
            "今日抓取内容较少，建议重点复核数据源状态",
            "当前更适合关注节日节点与后续补充更新",
        ]

    consumer_titles = [x.get("display_title") or x.get("title", "") for x in consumer_news[:6]]
    channel_titles = [x.get("display_title") or x.get("title", "") for x in channel_news[:6]]
    product_titles = [x.get("display_title") or x.get("name", "") for x in products[:6]]

    prompt = f"""你是消费电子行业分析师，请基于以下信息生成【今日重点】。

要求：
1. 输出3-5条
2. 每条一句话
3. 必须有“判断”，不是简单复述标题
4. 用中文
5. 每条控制在30字以内
6. 风格像内部业务简报
7. 优先关注耳机/音频、渠道变化、新品趋势

今日热点：
{consumer_titles}

渠道新闻：
{channel_titles}

新品：
{product_titles}
"""

    fallback = [
        "音频与消费电子新品仍是今日关注重点",
        "渠道侧更值得关注平台与零售动态变化",
        "建议优先跟进可转化为销售动作的信息",
    ]

    if client is None:
        return fallback

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是资深消费电子行业分析师"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        text = (response.choices[0].message.content or "").strip()
        lines = [
            x.strip().lstrip("-•").lstrip("1234567890.、").strip()
            for x in text.splitlines()
            if x.strip()
        ]
        lines = [x for x in lines if x]
        return lines[:5] if lines else fallback

    except Exception as e:
        logger.warning(f"Takeaways generation failed: {e}")
        return fallback


def detect_tags(text: str, bucket: str = "") -> List[str]:
    t = (text or "").lower()
    tags: List[str] = []

    tag_rules = [
        (
            "🎧 耳机音频",
            [
                "headphones", "earbuds", "earbud", "headset", "speaker",
                "audio", "anc", "noise cancelling", "open-ear", "open ear",
                "bone conduction", "bose", "beats", "soundcore", "jbl",
                "sennheiser", "shokz", "sony wf", "sony wh", "airpods",
            ],
        ),
        (
            "🏃 穿戴运动",
            [
                "garmin", "smartwatch", "wearable", "fitness tracker",
                "running watch", "health", "sports watch", "watch",
            ],
        ),
        (
            "🚁 无人机影像",
            [
                "drone", "dji", "gopro", "insta360", "osmo",
                "action camera", "camera",
            ],
        ),
        (
            "🛒 渠道零售",
            [
                "retail", "retailer", "store", "distribution", "channel",
                "merchant", "sell-through", "sell in",
            ],
        ),
        (
            "🏬 平台电商",
            [
                "amazon", "walmart", "best buy", "target", "costco",
                "tiktok shop", "e-commerce", "ecommerce", "marketplace",
                "platform",
            ],
        ),
        (
            "🚀 新品发布",
            [
                "launch", "launches", "launched", "release", "released",
                "announces", "announced", "unveil", "unveiled", "debut",
                "debuts", "new model", "available",
            ],
        ),
        (
            "👔 高管组织",
            [
                "ceo", "cmo", "executive", "president", "leadership",
                "appoints", "appointed", "organization", "restructure",
            ],
        ),
        (
            "💰 价格促销",
            [
                "price", "pricing", "discount", "sale", "promotion",
                "deal", "markdown", "coupon",
            ],
        ),
    ]

    for tag, keywords in tag_rules:
        if any(kw in t for kw in keywords):
            tags.append(tag)

    if not tags and bucket == "consumer_electronics":
        tags.append("📱 消费电子")
    if not tags and bucket == "channel_news":
        tags.append("🛒 渠道动态")
    if not tags and bucket == "products":
        tags.append("🚀 新品")

    return tags[:3]


def build_tag_text(item: Dict[str, Any], bucket: str = "") -> List[str]:
    text = " ".join(
        [
            item.get("title", "") or item.get("name", ""),
            item.get("summary", ""),
            item.get("source", ""),
        ]
    )
    return detect_tags(text, bucket)


def build_placeholder_item(title: str, bucket: str) -> Dict[str, Any]:
    return {
        "title": title,
        "display_title": title,
        "summary": "",
        "url": "#",
        "source": "system",
        "bucket": bucket,
        "tags": ["📭 暂无更新"],
        "_score": -1,
    }


def build_placeholder_product(title: str) -> Dict[str, Any]:
    return {
        "name": title,
        "display_title": title,
        "display_summary": "当前新品源暂无有效更新",
        "summary": "",
        "url": "#",
        "source": "system",
        "tags": ["📭 暂无更新"],
        "_score": -1,
    }


def main() -> None:
    news = load_json("data/raw/news.json", {})
    products = load_json("data/raw/products.json", {"products": []})
    festivals = load_json(
        "data/processed/festivals.json",
        {"festival_cards": [], "festival_pages": []},
    )
    config = load_yaml("config/news_sources.yaml")

    consumer = filter_valid_items(
        dedupe(news.get("consumer_electronics", [])),
        "title",
    )
    channel = filter_valid_items(
        dedupe(news.get("channel_news", [])),
        "title",
    )
    product_items = filter_valid_items(
        dedupe(products.get("products", [])),
        "name",
    )

    logger.info(
        f"Loaded raw content | consumer={len(consumer)}, "
        f"channel={len(channel)}, products={len(product_items)}"
    )

    consumer_source_priority = build_source_priority(
        config["sources"].get("consumer_electronics", [])
    )
    channel_source_priority = build_source_priority(
        config["sources"].get("channel_news", [])
    )
    keyword_conf = config.get("keywords", {})

    for x in consumer:
        x["_score"] = score_item(
            x,
            "consumer_electronics",
            consumer_source_priority,
            keyword_conf,
        )
        x["display_title"] = simplify_title(x.get("title", ""))
        x["tags"] = build_tag_text(x, "consumer_electronics")

    consumer = sorted(consumer, key=lambda x: x["_score"], reverse=True)[:9]

    for x in channel:
        x["_score"] = score_item(
            x,
            "channel_news",
            channel_source_priority,
            keyword_conf,
        )
        x["display_title"] = simplify_title(x.get("title", ""))
        x["tags"] = build_tag_text(x, "channel_news")

    channel = sorted(channel, key=lambda x: x["_score"], reverse=True)[:9]

    product_items = product_items[:6]
    for x in product_items:
        name = x.get("name", "")
        summary = x.get("summary", "")
        x["display_title"] = simplify_title(name) or name
        x["display_summary"] = simplify_summary(summary) or summary
        x["tags"] = build_tag_text(x, "products")

    if not consumer:
        consumer = [build_placeholder_item("今日消费电子新闻暂无有效更新", "consumer_electronics")]

    if not channel:
        channel = [build_placeholder_item("今日渠道新闻暂无有效更新", "channel_news")]

    if not product_items:
        product_items = [build_placeholder_product("今日新品暂无有效更新")]

    payload = {
        "date": str(date.today()),
        "festival_cards": festivals.get("festival_cards", []),
        "festival_pages": festivals.get("festival_pages", []),
        "consumer_electronics": consumer,
        "channel_news": channel,
        "products": product_items,
        "takeaways": generate_takeaways(consumer, channel, product_items),
    }

    dump_json("data/processed/daily_payload.json", payload)
    logger.info(
        f"Saved data/processed/daily_payload.json | "
        f"consumer={len(consumer)}, channel={len(channel)}, products={len(product_items)}, "
        f"takeaways={len(payload['takeaways'])}"
    )


if __name__ == "__main__":
    main()
