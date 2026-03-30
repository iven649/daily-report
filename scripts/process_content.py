from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from common import (
    build_dedupe_key,
    dump_json,
    format_local_timestamp,
    freshness_label,
    hours_since,
    is_meaningful_text,
    load_json,
    load_yaml,
    logger,
    normalize_text,
    now_utc,
    parse_datetime,
    today_local,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

MAX_DISPLAY_AGE_HOURS = 24 * 45  # 45天以上的内容直接不展示，避免过旧文章混入


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
                {"role": "system", "content": "你是一个资深北美消费电子行业编辑"},
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


def ai_json(prompt: str) -> Dict[str, Any]:
    if client is None:
        return {}

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是北美消费电子业务分析师。只输出合法 JSON，不要 markdown，不要解释。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = (response.choices[0].message.content or "").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning(f"AI json parse failed: {e}")
        return {}


def simplify_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return ""

    prompt = f"""请把下面标题改写成简短中文标题，适合北美业务日报使用。
要求：
1. 18字以内
2. 避免空话
3. 尽量保留品牌/平台/关键信息

标题：
{title}
"""
    return ai_generate(prompt, title, 24)


def simplify_summary(summary: str) -> str:
    summary = (summary or "").strip()
    if not summary:
        return ""

    prompt = f"""请把下面内容改写成中文摘要。
要求：
1. 40字以内
2. 偏业务信息，不要泛化
3. 适合日报卡片展示

内容：
{summary}
"""
    return ai_generate(prompt, summary, 46)

def smart_truncate_title(text: str, max_chars: int = 42) -> str:
    text = " ".join((text or "").split()).strip()
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    words = text.split(" ")
    if len(words) <= 1:
        return text[: max_chars - 3].rstrip(" ,.-_/") + "..."

    kept = []
    current_len = 0
    limit = max_chars - 3

    for word in words:
        extra = len(word) if not kept else len(word) + 1
        if current_len + extra > limit:
            break
        kept.append(word)
        current_len += extra

    if not kept:
        return text[: max_chars - 3].rstrip(" ,.-_/") + "..."

    result = " ".join(kept).rstrip(" ,.-_/")
    return result + "..."


def classify_product_judgement(item: Dict[str, Any]) -> str:
    text = normalize_text(
        " ".join(
            [
                item.get("name", ""),
                item.get("title", ""),
                item.get("summary", ""),
                item.get("source", ""),
            ]
        )
    )

    if any(x in text for x in ["deal", "discount", "promotion", "sale", "pricing", "coupon"]):
        return "价格促销"

    if any(
        x in text
        for x in [
            "amazon", "walmart", "best buy", "target", "marketplace",
            "retail", "store", "distribution", "channel", "rei", "fleet feet"
        ]
    ):
        return "渠道动态"

    if any(x in text for x in ["launch", "release", "announce", "unveil", "debut", "available", "new app"]):
        return "新品发布"

    if any(x in text for x in ["apple", "beats", "bose", "sony", "shokz", "garmin", "jbl", "anker", "sennheiser"]):
        return "竞品观察"

    if any(x in text for x in ["trend", "trends", "market", "category", "wearable", "audio", "headphone", "earbuds"]):
        return "行业趋势"

    if any(x in text for x in ["ban", "lawsuit", "recall", "investigation", "policy", "regulation"]):
        return "重大事件"

    return "业务观察"


def build_product_intro(item: Dict[str, Any]) -> str:
    summary = " ".join((item.get("display_summary") or item.get("summary") or "").split()).strip()
    title = " ".join((item.get("name") or item.get("title") or "").split()).strip()
    text = normalize_text(" ".join([title, summary, item.get("source", "")]))

    if summary:
        summary = summary.rstrip("。.;；:：,， ")

    if summary:
        if len(summary) > 40:
            summary = smart_truncate_title(summary, 40).rstrip(".")
        if not summary.endswith("。"):
            summary += "。"
        return summary

    if any(x in text for x in ["open-ear", "open ear", "bone conduction", "headphone", "earbuds", "audio"]):
        return "聚焦音频品类与使用场景变化。"

    if any(x in text for x in ["wearable", "watch", "fitness", "running", "sports"]):
        return "聚焦穿戴设备与运动场景动向。"

    if any(x in text for x in ["amazon", "walmart", "best buy", "retail", "channel", "store"]):
        return "反映平台或渠道端的新品与动作。"

    if any(x in text for x in ["launch", "release", "announce", "unveil", "debut"]):
        return "可作为新品发布节奏的观察样本。"

    return "建议纳入北美新品观察清单。"

def build_source_priority(source_list: List[Dict[str, Any]]) -> Dict[str, int]:
    return {s["name"]: s.get("priority", 0) for s in source_list}


def detect_monitor_hits(text: str, monitoring: Dict[str, Any]) -> Dict[str, List[str]]:
    t = normalize_text(text)

    def match_list(items: List[str]) -> List[str]:
        hits = []
        for item in items:
            key = normalize_text(item)
            if key and key in t:
                hits.append(item)
        return hits

    return {
        "brands": match_list(monitoring.get("brands", [])),
        "channels": match_list(monitoring.get("channels", [])),
        "categories": match_list(monitoring.get("categories", [])),
    }


def market_bias_score(text: str) -> int:
    t = normalize_text(text)

    us_terms = [
        "amazon", "best buy", "walmart", "target", "costco", "sam's club",
        "sams club", "fleet feet", "rei", "u.s.", "us", "north america",
        "american", "retail", "store", "marketplace",
    ]
    cn_terms = [
        "china", "chinese", "jd.com", "tmall", "taobao", "wechat", "alibaba",
        "shenzhen",
    ]

    score = 0
    score += sum(1 for x in us_terms if x in t) * 8
    score += sum(1 for x in cn_terms if x in t) * 2
    return score


def freshness_score(hours: Optional[float], conf: Dict[str, Any]) -> int:
    if hours is None:
        return -3

    decay_after = conf["decay_after_hours"]
    normal_window = conf["normal_window_hours"]
    soft_limit = conf["soft_limit_hours"]
    hard_limit = conf["hard_limit_hours"]

    if hours <= decay_after:
        return 35
    if hours <= normal_window:
        return 20
    if hours <= soft_limit:
        return 5
    if hours <= hard_limit:
        return -15
    return -60


def is_too_old(item: Dict[str, Any]) -> bool:
    published_iso = item.get("published_iso", "")
    if not published_iso:
        return False
    hours = hours_since(parse_datetime(published_iso))
    if hours is None:
        return False
    return hours > MAX_DISPLAY_AGE_HOURS


def filter_recent_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [x for x in items if not is_too_old(x)]


def detect_tags(text: str, bucket: str = "") -> List[str]:
    t = normalize_text(text)
    tags: List[str] = []

    tag_rules = [
        ("🎧 耳机音频", ["headphones", "headphone", "earbuds", "earbud", "audio", "open-ear", "bone conduction"]),
        ("🏃 运动穿戴", ["wearable", "smartwatch", "fitness", "running", "garmin"]),
        ("🚁 无人机影像", ["drone", "uav", "dji", "action camera", "camera"]),
        ("🛒 渠道零售", ["retail", "store", "distribution", "channel", "fleet feet", "rei"]),
        ("🏬 平台电商", ["amazon", "walmart", "best buy", "target", "costco", "sam's club", "marketplace"]),
        ("🚀 新品发布", ["launch", "release", "announce", "unveil", "debut", "available"]),
        ("💰 价格促销", ["price", "pricing", "discount", "promotion", "deal"]),
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


def decide_impact_area(item: Dict[str, Any]) -> str:
    channels = item.get("monitor_hits", {}).get("channels", [])
    categories = item.get("monitor_hits", {}).get("categories", [])
    brands = item.get("monitor_hits", {}).get("brands", [])
    text = normalize_text(
        " ".join(
            [
                item.get("title", "") or item.get("name", ""),
                item.get("summary", ""),
            ]
        )
    )

    if channels or any(x in text for x in ["marketplace", "ecommerce", "e-commerce", "promotion", "deal", "traffic"]):
        return "电商"
    if any(x in text for x in ["retail", "store", "distribution", "channel", "partnership"]) or "Fleet Feet" in channels or "REI" in channels:
        return "渠道销售"
    if brands or categories:
        return "品牌营销"
    return "品牌营销"


def fallback_business_note(item: Dict[str, Any]) -> str:
    brands = item.get("monitor_hits", {}).get("brands", [])
    channels = item.get("monitor_hits", {}).get("channels", [])
    categories = item.get("monitor_hits", {}).get("categories", [])
    area = item.get("impact_area", "品牌营销")

    if channels:
        return f"北美渠道侧出现与{' / '.join(channels[:2])}相关信号，优先评估对{area}的影响。"
    if brands:
        return f"{' / '.join(brands[:2])}相关动态值得纳入北美竞品观察，关注品牌动作与市场声量。"
    if categories:
        return f"{' / '.join(categories[:2])}相关趋势仍有热度，建议结合北美用户场景判断机会。"
    return f"该条内容与{area}相关，建议作为北美业务观察样本继续跟踪。"


def fallback_suggested_action(item: Dict[str, Any]) -> str:
    area = item.get("impact_area", "品牌营销")
    if area == "电商":
        return "关注平台价格、流量和活动节奏，必要时补充竞品页面巡检。"
    if area == "渠道销售":
        return "跟进渠道伙伴与零售侧变化，评估是否影响铺货与合作沟通。"
    return "关注品牌话题和竞品动作，必要时补充传播与产品卖点分析。"


def fallback_importance(score: int) -> str:
    if score >= 120:
        return "高"
    if score >= 70:
        return "中"
    return "低"


def enrich_item_with_ai(item: Dict[str, Any]) -> Dict[str, Any]:
    title = item.get("title") or item.get("name", "")
    summary = item.get("summary", "")
    impact_area = item.get("impact_area", "品牌营销")
    monitor_hits = item.get("monitor_hits", {})
    brands = ", ".join(monitor_hits.get("brands", [])[:3]) or "无"
    channels = ", ".join(monitor_hits.get("channels", [])[:3]) or "无"
    categories = ", ".join(monitor_hits.get("categories", [])[:3]) or "无"

    prompt = f"""请基于以下北美消费电子行业信息输出 JSON：
{{
  "importance": "高/中/低",
  "business_note": "一句中文业务意义，45字以内",
  "suggested_action": "一句中文建议动作，45字以内"
}}

要求：
1. 受众是北美业务团队
2. 优先考虑 电商 / 品牌营销 / 渠道销售
3. 不要写空话，不要泛泛而谈
4. importance 只能是 高、中、低

标题：{title}
摘要：{summary}
已判断影响团队：{impact_area}
品牌命中：{brands}
平台/渠道命中：{channels}
品类命中：{categories}
"""

    result = ai_json(prompt)
    if not result:
        item["importance"] = fallback_importance(item.get("_score", 0))
        item["business_note"] = fallback_business_note(item)
        item["suggested_action"] = fallback_suggested_action(item)
        return item

    item["importance"] = result.get("importance") or fallback_importance(item.get("_score", 0))
    item["business_note"] = (result.get("business_note") or fallback_business_note(item))[:70]
    item["suggested_action"] = (result.get("suggested_action") or fallback_suggested_action(item))[:70]
    return item


def score_item(
    item: Dict[str, Any],
    bucket: str,
    source_priority: Dict[str, int],
    keyword_conf: Dict[str, Any],
    freshness_conf: Dict[str, Any],
    monitoring: Dict[str, Any],
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

    score += sum(30 for kw in high_keywords if kw.lower() in text)
    score += sum(10 for kw in medium_keywords if kw.lower() in text)

    hits = detect_monitor_hits(text, monitoring)
    score += len(hits["brands"]) * 22
    score += len(hits["channels"]) * 24
    score += len(hits["categories"]) * 18

    if bucket == "channel_news" and hits["channels"]:
        score += 15
    if bucket == "consumer_electronics" and hits["brands"]:
        score += 12

    parsed_hours = None
    published_iso = item.get("published_iso", "")
    if published_iso:
        parsed_hours = hours_since(parse_datetime(published_iso))

    score += freshness_score(parsed_hours, freshness_conf)
    score += market_bias_score(text)

    if len(title) > 140:
        score -= 5

    item["hours_since_published"] = round(parsed_hours, 1) if parsed_hours is not None else None
    item["freshness_label"] = freshness_label(parsed_hours)
    item["monitor_hits"] = hits

    return score


def generate_takeaways(
    lead_story: Optional[Dict[str, Any]],
    consumer_news: List[Dict[str, Any]],
    channel_news: List[Dict[str, Any]],
    products: List[Dict[str, Any]],
) -> List[str]:
    if not consumer_news and not channel_news and not products:
        return [
            "今日有效抓取较少，建议先检查 RSS 源与发布时间分布。",
            "当前更适合关注节日节点及后续补充更新。",
        ]

    lead = lead_story.get("display_title", "") if lead_story else ""
    consumer_titles = [x.get("display_title") or x.get("title", "") for x in consumer_news[:5]]
    channel_titles = [x.get("display_title") or x.get("title", "") for x in channel_news[:5]]
    product_titles = [x.get("display_title") or x.get("name", "") for x in products[:4]]

    prompt = f"""你是北美消费电子业务分析师，请生成【今日重点】。
要求：
1. 输出 3-5 条
2. 每条一句中文
3. 必须带判断，不要复述新闻
4. 偏北美市场，优先平台、电商、渠道与竞品
5. 每条控制在 34 字以内

头条：
{lead}

消费电子：
{consumer_titles}

渠道平台：
{channel_titles}

新品：
{product_titles}
"""

    fallback = [
        "北美平台与零售动态仍是今天最值得跟进的外部信号。",
        "耳机与运动音频相关品类依然是竞品观察重点。",
        "新品与渠道信息更适合结合价格、铺货和传播动作一起看。",
    ]

    if client is None:
        return fallback

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是资深北美消费电子行业分析师"},
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


def generate_lead_summary(lead_story: Optional[Dict[str, Any]], takeaways: List[str]) -> str:
    if lead_story is None:
        return "今日暂无足够强的头条信号，建议重点关注后续更新。"

    fallback = takeaways[0] if takeaways else (lead_story.get("business_note") or "北美市场今日重点仍集中在平台与竞品变化。")
    prompt = f"""请基于以下信息生成一句适合放在日报顶部的总判断。
要求：
1. 中文
2. 30字以内
3. 要像老板能一眼看懂的总结
4. 不要只是改写标题

头条标题：{lead_story.get("display_title") or lead_story.get("title") or lead_story.get("name")}
业务意义：{lead_story.get("business_note", "")}
今日重点候选：{takeaways[:3]}
"""
    return ai_generate(prompt, fallback, 40)


def generate_signal_block(
    signal_name: str,
    items: List[Dict[str, Any]],
    mode: str,
) -> List[str]:
    if not items:
        return ["今日暂无足够信号。"]

    source_lines = []
    for item in items[:6]:
        source_lines.append(
            f"- {item.get('display_title') or item.get('title') or item.get('name')} | "
            f"{item.get('impact_area', '')} | {item.get('business_note', '')}"
        )

    prompt = f"""你是北美消费电子业务分析师，请输出 {signal_name}。
要求：
1. 输出 2-3 条
2. 每条一句中文
3. 不能空泛
4. 必须适合管理层快速看
5. 如果是{mode}，要体现{mode}的业务判断

素材：
{source_lines}
"""

    fallback = []
    for item in items[:2]:
        if mode == "机会":
            fallback.append(item.get("business_note") or "北美市场出现值得跟进的新机会。")
        else:
            fallback.append(item.get("suggested_action") or "建议关注潜在风险信号。")

    if client is None:
        return fallback[:3] if fallback else ["今日暂无足够信号。"]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是资深北美消费电子行业分析师"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
        )
        text = (response.choices[0].message.content or "").strip()
        lines = [
            x.strip().lstrip("-•").lstrip("1234567890.、").strip()
            for x in text.splitlines()
            if x.strip()
        ]
        return lines[:3] if lines else (fallback[:3] if fallback else ["今日暂无足够信号。"])
    except Exception as e:
        logger.warning(f"{signal_name} generation failed: {e}")
        return fallback[:3] if fallback else ["今日暂无足够信号。"]


def build_placeholder_item(title: str, bucket: str) -> Dict[str, Any]:
    return {
        "title": title,
        "display_title": title,
        "summary": "",
        "url": "#",
        "source": "system",
        "bucket": bucket,
        "tags": ["📭 暂无更新"],
        "monitor_hits": {"brands": [], "channels": [], "categories": []},
        "impact_area": "品牌营销",
        "importance": "低",
        "business_note": "当前没有足够有效内容，建议关注后续更新。",
        "suggested_action": "先复核数据源状态，再等待下一轮抓取。",
        "freshness_label": "时间未知",
        "_score": -1,
    }


def build_placeholder_product(title: str) -> Dict[str, Any]:
    return {
        "name": title,
        "display_title": smart_truncate_title(title, 42),
        "display_summary": "当前新品源暂无有效更新",
        "product_intro": "当前新品源暂无有效更新。",
        "judgement_label": "暂无更新",
        "summary": "",
        "url": "#",
        "source": "system",
        "tags": ["📭 暂无更新"],
        "monitor_hits": {"brands": [], "channels": [], "categories": []},
        "impact_area": "品牌营销",
        "importance": "低",
        "business_note": "当前没有足够新品信息，适合继续观察竞品发布窗口。",
        "suggested_action": "维持监控，等待下一轮抓取。",
        "freshness_label": "时间未知",
        "_score": -1,
    }


def build_entity_watchlist(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pool: Dict[str, Dict[str, Any]] = {}

    for item in items:
        hits = item.get("monitor_hits", {})
        for brand in hits.get("brands", []):
            pool.setdefault(brand, {"name": brand, "type": "品牌", "count": 0, "items": []})
            pool[brand]["count"] += 1
            pool[brand]["items"].append(item)
        for channel in hits.get("channels", []):
            pool.setdefault(channel, {"name": channel, "type": "渠道", "count": 0, "items": []})
            pool[channel]["count"] += 1
            pool[channel]["items"].append(item)
        for category in hits.get("categories", []):
            pool.setdefault(category, {"name": category, "type": "品类", "count": 0, "items": []})
            pool[category]["count"] += 1
            pool[category]["items"].append(item)

    result = []
    for _, obj in pool.items():
        obj["items"] = sorted(obj["items"], key=lambda x: x.get("_score", 0), reverse=True)[:2]
        result.append(obj)

    result.sort(key=lambda x: (x["count"], x["type"] == "渠道"), reverse=True)
    return result[:8]


def build_us_timezones() -> List[Dict[str, str]]:
    return [
        {"name": "Eastern", "abbr": "ET"},
        {"name": "Central", "abbr": "CT"},
        {"name": "Mountain", "abbr": "MT"},
        {"name": "Pacific", "abbr": "PT"},
        {"name": "Alaska", "abbr": "AKT"},
        {"name": "Hawaii", "abbr": "HST"},
    ]


def pick_headline_trio(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    picked: List[Dict[str, Any]] = []
    seen_keys = set()

    for item in sorted(items, key=lambda x: x.get("_score", 0), reverse=True):
        title = item.get("display_title") or item.get("title") or item.get("name", "")
        key = build_dedupe_key(title=title, summary=item.get("summary", ""))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        picked.append(item)
        if len(picked) >= 3:
            break

    return picked


def main() -> None:
    news = load_json("data/raw/news.json", {})
    products = load_json("data/raw/products.json", {"products": []})
    festivals = load_json(
        "data/processed/festivals.json",
        {"festival_cards": [], "festival_pages": []},
    )
    news_config = load_yaml("config/news_sources.yaml")
    product_config = load_yaml("config/product_sources.yaml")
    monitoring_conf = load_yaml("config/monitoring.yaml")

    freshness_conf = monitoring_conf.get("freshness", {})
    monitoring = monitoring_conf.get("monitoring", {})

    consumer = filter_valid_items(dedupe(news.get("consumer_electronics", [])), "title")
    channel = filter_valid_items(dedupe(news.get("channel_news", [])), "title")
    product_items = filter_valid_items(dedupe(products.get("products", [])), "name")

    consumer = filter_recent_items(consumer)
    channel = filter_recent_items(channel)
    product_items = filter_recent_items(product_items)

    logger.info(
        f"Loaded raw content | consumer={len(consumer)}, channel={len(channel)}, products={len(product_items)}"
    )

    consumer_source_priority = build_source_priority(
        news_config["sources"].get("consumer_electronics", [])
    )
    channel_source_priority = build_source_priority(
        news_config["sources"].get("channel_news", [])
    )
    keyword_conf = news_config.get("keywords", {})

    product_keyword_conf = product_config.get("keywords", {})
    product_source_priority = build_source_priority(
        product_config["sources"].get("products", [])
    )

    for x in consumer:
        x["_score"] = score_item(
            x,
            "consumer_electronics",
            consumer_source_priority,
            keyword_conf,
            freshness_conf,
            monitoring,
        )
        x["display_title"] = simplify_title(x.get("title", "")) or x.get("title", "")
        x["tags"] = detect_tags(
            " ".join([x.get("title", ""), x.get("summary", ""), x.get("source", "")]),
            "consumer_electronics",
        )
        x["impact_area"] = decide_impact_area(x)

    for x in channel:
        x["_score"] = score_item(
            x,
            "channel_news",
            channel_source_priority,
            keyword_conf,
            freshness_conf,
            monitoring,
        )
        x["display_title"] = simplify_title(x.get("title", "")) or x.get("title", "")
        x["tags"] = detect_tags(
            " ".join([x.get("title", ""), x.get("summary", ""), x.get("source", "")]),
            "channel_news",
        )
        x["impact_area"] = decide_impact_area(x)

    for x in product_items:
        x["_score"] = score_item(
            x,
            "consumer_electronics",
            product_source_priority,
            {"consumer_electronics": product_keyword_conf},
            freshness_conf,
            monitoring,
        )
        name = x.get("name", "")
        summary = x.get("summary", "")
        x["display_title"] = smart_truncate_title(name, 42) or name
        x["display_summary"] = simplify_summary(summary) or summary
        x["tags"] = detect_tags(
            " ".join([name, summary, x.get("source", "")]),
            "products",
        )
        x["impact_area"] = decide_impact_area(x)
        x["judgement_label"] = classify_product_judgement(x)
        x["product_intro"] = build_product_intro(x)

    consumer = sorted(consumer, key=lambda x: x["_score"], reverse=True)[:10]
    channel = sorted(channel, key=lambda x: x["_score"], reverse=True)[:10]
    product_items = sorted(product_items, key=lambda x: x["_score"], reverse=True)[:6]

    if not consumer:
        consumer = [build_placeholder_item("今日消费电子新闻暂无有效更新", "consumer_electronics")]
    if not channel:
        channel = [build_placeholder_item("今日渠道新闻暂无有效更新", "channel_news")]
    if not product_items:
        product_items = [build_placeholder_product("今日新品暂无有效更新")]

    enrich_pool: List[Dict[str, Any]] = []
    for section in [consumer[:6], channel[:6], product_items[:6]]:
        for item in section:
            if item not in enrich_pool:
                enrich_pool.append(item)

    for item in enrich_pool:
        enrich_item_with_ai(item)

    all_ranked = sorted(consumer + channel + product_items, key=lambda x: x.get("_score", 0), reverse=True)
    headline_trio = pick_headline_trio(all_ranked)
    lead_story = headline_trio[0] if headline_trio else (all_ranked[0] if all_ranked else None)

    if lead_story and lead_story not in enrich_pool:
        enrich_item_with_ai(lead_story)

    monitored_entities = build_entity_watchlist(consumer + channel + product_items)

    opportunity_source = sorted(
        [x for x in all_ranked if x.get("importance") in ["高", "中"] and x.get("impact_area") in ["电商", "品牌营销"]],
        key=lambda x: x.get("_score", 0),
        reverse=True,
    )
    risk_source = sorted(
        [x for x in all_ranked if x.get("impact_area") in ["渠道销售", "电商"]],
        key=lambda x: x.get("_score", 0),
        reverse=True,
    )

    takeaways = generate_takeaways(lead_story, consumer, channel, product_items)
    lead_summary = generate_lead_summary(lead_story, takeaways)
    opportunity_signals = generate_signal_block("机会提示", opportunity_source, "机会")
    risk_signals = generate_signal_block("风险提示", risk_source, "风险")

    payload = {
        "date": str(today_local()),
        "generated_at": format_local_timestamp("%Y-%m-%d %H:%M:%S %Z"),
        "market_focus": "美国优先，中国次之",
        "openai_enabled": bool(client),
        "festival_cards": festivals.get("festival_cards", []),
        "festival_pages": festivals.get("festival_pages", []),
        "us_timezones": build_us_timezones(),
        "lead_story": lead_story,
        "lead_summary": lead_summary,
        "headline_trio": headline_trio,
        "consumer_electronics": consumer[:6],
        "channel_news": channel[:6],
        "products": product_items,
        "monitored_entities": monitored_entities,
        "takeaways": takeaways,
        "opportunity_signals": opportunity_signals,
        "risk_signals": risk_signals,
        "feedback_items": [
            "这期日报最有价值的是哪一块？",
            "哪些内容你觉得太多、太少，或还缺失？",
            "哪些品牌 / 平台 / 品类应该被提升到更高优先级？",
            "哪些判断不够准确，应该怎么改？",
        ],
        "status": {
            "consumer_count": len(consumer),
            "channel_count": len(channel),
            "product_count": len(product_items),
            "source_summary": "消费电子 / 渠道 / 新品 三类源已完成抓取与筛选",
            "freshness_rule": "24h后开始降权",
        },
    }

    dump_json("data/processed/daily_payload.json", payload)
    logger.info(
        "Saved data/processed/daily_payload.json | "
        f"date={payload['date']}, generated_at={payload['generated_at']}, "
        f"consumer={len(consumer)}, channel={len(channel)}, "
        f"products={len(product_items)}, entities={len(monitored_entities)}"
    )


if __name__ == "__main__":
    main()
