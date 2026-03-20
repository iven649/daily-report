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

    score += source_priority.get(source, 0) * 10

    bucket_keywords = keyword_conf.get(bucket, {})
    high_keywords = bucket_keywords.get("high", [])
    medium_keywords = bucket_keywords.get("medium", [])

    for kw in high_keywords:
        if kw.lower() in title:
            score += 30

    for kw in medium_keywords:
        if kw.lower() in title:
            score += 10

    if len(title) > 120:
        score -= 5

    return score


def build_source_priority(source_list: List[Dict[str, Any]]) -> Dict[str, int]:
    result = {}
    for s in source_list:
        result[s["name"]] = s.get("priority", 0)
    return result


def generate_takeaways(consumer_news: List[Dict[str, Any]], channel_news: List[Dict[str, Any]]) -> List[str]:
    consumer_titles = [x.get("title", "") for x in consumer_news[:5] if x.get("title")]
    channel_titles = [x.get("title", "") for x in channel_news[:5] if x.get("title")]

    prompt = f"""你是消费电子行业分析师，请基于以下新闻生成 3 条「今日重点」。

要求：
1. 中文
2. 每条 18-28 字左右
3. 不是简单复述标题，而是提炼方向和判断
4. 适合出现在部门日报首页
5. 只输出 3 行，不要加解释

【今日热点】
{consumer_titles}

【渠道新闻】
{channel_titles}
"""

    fallback = [
        "关注消费电子硬件与音频新品动态",
        "关注渠道侧平台与零售变化信号",
        "优先跟进可转化为销售动作的信息",
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个资深消费电子行业编辑，擅长写部门日报总结。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )

        text = response.choices[0].message.content.strip()
        lines = [line.strip(" -•1234567890.、") for line in text.splitlines() if line.strip()]
        lines = [x for x in lines if x]

        if len(lines) >= 3:
            return lines[:3]

        return fallback

    except Exception as e:
        print(f"[WARN] 今日重点生成失败: {e}")
        return fallback

def detect_tags(text: str, bucket: str = "") -> List[str]:
    t = (text or "").lower()
    tags: List[str] = []

    tag_rules = [
        ("🎧 耳机音频", [
            "headphones", "earbuds", "earbud", "headset", "speaker",
            "audio", "anc", "noise cancelling", "open-ear", "open ear",
            "bone conduction", "bose", "beats", "soundcore", "jbl",
            "sennheiser", "shokz", "sony wf", "sony wh", "airpods"
        ]),
        ("🏃 穿戴运动", [
            "garmin", "smartwatch", "wearable", "fitness tracker",
            "running watch", "health", "sports watch", "watch"
        ]),
        ("🚁 无人机影像", [
            "drone", "dji", "gopro", "insta360", "osmo",
            "action camera", "camera"
        ]),
        ("🛒 渠道零售", [
            "retail", "retailer", "store", "distribution", "channel",
            "merchant", "sell-through", "sell in"
        ]),
        ("🏬 平台电商", [
            "amazon", "walmart", "best buy", "target", "costco",
            "tiktok shop", "e-commerce", "ecommerce", "marketplace",
            "platform"
        ]),
        ("🚀 新品发布", [
            "launch", "launches", "launched", "release", "released",
            "announces", "announced", "unveil", "unveiled", "debut",
            "debuts", "new model", "available"
        ]),
        ("👔 高管组织", [
            "ceo", "cmo", "executive", "president", "leadership",
            "appoints", "appointed", "organization", "restructure"
        ]),
        ("💰 价格促销", [
            "price", "pricing", "discount", "sale", "promotion",
            "deal", "markdown", "coupon"
        ]),
    ]

    for tag, keywords in tag_rules:
        if any(kw in t for kw in keywords):
            tags.append(tag)

    # 按模块兜底补一个标签
    if not tags and bucket == "consumer_electronics":
        tags.append("📱 消费电子")
    if not tags and bucket == "channel_news":
        tags.append("🛒 渠道动态")
    if not tags and bucket == "products":
        tags.append("🚀 新品")

    return tags[:3]


def build_tag_text(item: Dict[str, Any], bucket: str = "") -> List[str]:
    text = " ".join([
        item.get("title", "") or item.get("name", ""),
        item.get("summary", ""),
        item.get("source", "")
    ])
    return detect_tags(text, bucket)

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

    for x in consumer:
        x["_score"] = score_item(
            x,
            "consumer_electronics",
            consumer_source_priority,
            keyword_conf
        )
        x["display_title"] = simplify_title(x.get("title", ""))
        x["tags"] = build_tag_text(x, "consumer_electronics")

    consumer = sorted(consumer, key=lambda x: x["_score"], reverse=True)[:9]

    for x in channel:
        x["_score"] = score_item(
            x,
            "channel_news",
            channel_source_priority,
            keyword_conf
        )
        x["display_title"] = simplify_title(x.get("title", ""))
        x["tags"] = build_tag_text(x, "channel_news")

    channel = sorted(channel, key=lambda x: x["_score"], reverse=True)[:9]

    product_items = dedupe(products.get("products", []))[:6]

    for x in product_items:
        name = x.get("name", "")
        summary = x.get("summary", "")
        x["display_title"] = simplify_title(name) or name
        x["display_summary"] = simplify_summary(summary) or summary
        x["tags"] = build_tag_text(x, "products")

    takeaways = generate_takeaways(consumer, channel)

    payload = {
        "date": str(date.today()),
        "festival_cards": festivals.get("festival_cards", []),
        "festival_pages": festivals.get("festival_pages", []),
        "consumer_electronics": consumer,
        "channel_news": channel,
        "products": product_items,
        "takeaways": takeaways,
    }

    dump_json("data/processed/daily_payload.json", payload)
    print("[OK] payload generated")


if __name__ == "__main__":
    main()
