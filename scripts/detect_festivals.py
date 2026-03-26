from __future__ import annotations

from datetime import date, timedelta

from dateutil.easter import easter

from common import dump_json, load_yaml, logger


def nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    if nth > 0:
        d = date(year, month, 1)
        while d.weekday() != weekday:
            d += timedelta(days=1)
        d += timedelta(days=(nth - 1) * 7)
        return d

    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)

    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def resolve_base_dates_for_year(conf: dict, year: int) -> dict:
    result = {}

    for item in conf["festivals"]:
        rule = item["rule"]

        if rule == "fixed":
            result[item["slug"]] = date(year, item["month"], item["day"])
        elif rule == "easter":
            result[item["slug"]] = easter(year)
        elif rule == "nth_weekday":
            result[item["slug"]] = nth_weekday_of_month(
                year,
                item["month"],
                item["weekday"],
                item["nth"],
            )

    for item in conf["festivals"]:
        if item["rule"] == "relative_to":
            ref = result[item["ref_slug"]]
            result[item["slug"]] = ref + timedelta(days=item["offset_days"])

    return result


def default_content(item: dict) -> dict:
    name = item["name"]
    market = item["market"]

    if market == "US":
        origin = f"{name}是美国市场的重要节日或零售节点。"
        story = "建议重点关注零售节奏、礼赠需求、平台流量与线下客流变化。"
        customs = ["家庭消费", "礼品采购", "平台促销", "线下零售活动"]
        consumption = ["礼赠类消费", "平台大促", "家庭出行与户外", "零售门店活动"]
        holiday = "具体活动强度以当年零售商、平台和品牌节奏为准。"
    elif market == "CN":
        origin = f"{name}是中国的重要节日或营销节点。"
        story = "可作为出海品牌供应链、内容营销和市场情绪的参考。"
        customs = ["节前备货", "礼赠需求", "节庆促销"]
        consumption = ["礼品零售", "出行相关", "节庆营销"]
        holiday = "当前页面以北美业务为主，中国节点仅作辅助参考。"
    else:
        origin = f"{name}是重要的电商营销节点。"
        story = "建议关注价格带变化、平台规则、广告竞争与库存节奏。"
        customs = ["平台大促", "价格竞争", "流量冲刺"]
        consumption = ["折扣活动", "广告投放", "库存与履约"]
        holiday = "属于营销节点，具体强度以平台和品牌策略为准。"

    return {
        "origin": origin,
        "story": story,
        "customs": customs,
        "consumption": consumption,
        "holiday": holiday,
    }


def choose_homepage_cards(items: list[dict]) -> list[dict]:
    upcoming = [x for x in items if 0 <= x["countdown"] <= 120]
    upcoming.sort(key=lambda x: (x["countdown"], -x.get("priority", 0)))

    us = [x for x in upcoming if x["market"] == "US"][:2]
    ecom = [x for x in upcoming if x["market"] == "ECOM"][:2]
    cn = [x for x in upcoming if x["market"] == "CN"][:1]

    picked = us + ecom

    used = {x["slug"] for x in picked}
    if len(picked) < 4:
        for item in cn:
            if item["slug"] not in used:
                picked.append(item)
                used.add(item["slug"])

    for item in upcoming:
        if item["slug"] not in used:
            picked.append(item)
            used.add(item["slug"])
        if len(picked) >= 4:
            break

    return picked[:4]


def main() -> None:
    today = date.today()
    conf = load_yaml("config/festivals.yaml")

    try:
        content_map = load_yaml("config/festival_content.yaml").get("content", {})
    except Exception:
        content_map = {}

    resolved = []

    for year in [today.year, today.year + 1]:
        dates_map = resolve_base_dates_for_year(conf, year)

        for item in conf["festivals"]:
            d = dates_map[item["slug"]]
            if d < today:
                continue

            merged = dict(item)
            merged["date"] = d.isoformat()
            merged["countdown"] = (d - today).days
            merged["year"] = d.year

            detail = default_content(item)
            detail.update(content_map.get(item["slug"], {}))
            merged.update(detail)

            resolved.append(merged)

    resolved.sort(key=lambda x: x["countdown"])

    deduped = []
    seen = set()
    for item in resolved:
        if item["slug"] in seen:
            continue
        seen.add(item["slug"])
        deduped.append(item)

    homepage = choose_homepage_cards(deduped)

    dump_json(
        "data/processed/festivals.json",
        {
            "today": today.isoformat(),
            "festival_cards": homepage,
            "festival_pages": deduped[:20],
        },
    )

    logger.info("Saved data/processed/festivals.json")


if __name__ == "__main__":
    main()
