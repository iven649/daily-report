from __future__ import annotations

from datetime import date, timedelta
from dateutil.easter import easter

from common import load_yaml, dump_json


def nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    # weekday: Monday=0 ... Sunday=6
    if nth > 0:
        d = date(year, month, 1)
        while d.weekday() != weekday:
            d += timedelta(days=1)
        d += timedelta(days=(nth - 1) * 7)
        return d

    # nth = -1 表示最后一个
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)

    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def resolve_base_dates_for_year(conf: dict, year: int) -> dict:
    result = {}

    # first pass: non-relative
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
                item["nth"]
            )

    # second pass: relative_to
    for item in conf["festivals"]:
        if item["rule"] == "relative_to":
            ref = result[item["ref_slug"]]
            result[item["slug"]] = ref + timedelta(days=item["offset_days"])

    return result


def default_content(item: dict) -> dict:
    name = item["name"]
    market = item["market"]
    ftype = item["type"]

    if market == "CN":
        origin = f"{name}是中国重要的节日或营销节点。"
        story = "建议关注礼赠、假期消费、出行与节前备货节奏。"
        customs = ["节前备货", "礼赠需求", "促销活动"]
        consumption = ["礼品零售", "出行相关", "节庆营销"]
        holiday = "具体放假安排以当年官方通知为准。"

    elif market == "US":
        origin = f"{name}是美国重要的节日或营销节点。"
        story = "建议关注零售节奏、家庭消费、礼赠及平台活动变化。"
        customs = ["家庭消费", "礼品采购", "节庆促销"]
        consumption = ["节庆礼赠", "平台流量", "零售活动"]
        holiday = "具体活动强度以当年零售商和平台节奏为准。"

    else:  # ECOM
        origin = f"{name}是重要的营销与促销节点。"
        story = "建议关注平台折扣、价格带变化、流量竞争与备货节奏。"
        customs = ["平台大促", "价格竞争", "流量冲刺"]
        consumption = ["折扣活动", "广告投放", "库存与履约"]
        holiday = "属于营销节点，具体节奏以平台和品牌策略为准。"

    return {
        "origin": origin,
        "story": story,
        "customs": customs,
        "consumption": consumption,
        "holiday": holiday,
    }


def choose_homepage_cards(items: list[dict]) -> list[dict]:
    # 首页建议最多展示 4 个，避免过满：
    # 1 个中国 + 1 个美国 + 2 个电商节点（如果有）
    upcoming = [x for x in items if 0 <= x["countdown"] <= 120]
    upcoming.sort(key=lambda x: (x["countdown"], -x.get("priority", 0)))

    cn = [x for x in upcoming if x["market"] == "CN"][:1]
    us = [x for x in upcoming if x["market"] == "US"][:1]
    ecom = [x for x in upcoming if x["market"] == "ECOM"][:2]

    picked = cn + us + ecom

    # 如果不足 4 个，用剩余最近节点补齐
    used = {x["slug"] for x in picked}
    for item in upcoming:
        if item["slug"] not in used:
            picked.append(item)
            used.add(item["slug"])
        if len(picked) >= 4:
            break

    return picked


def main():
    today = date.today()
    conf = load_yaml("config/festivals.yaml")

    # 如果你有更详细的内容库，会自动叠加；没有也不影响
    try:
        content_map = load_yaml("config/festival_content.yaml").get("content", {})
    except Exception:
        content_map = {}

    resolved = []

    # 计算当前年和下一年，确保跨年也有节点
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

    # 同一个 slug 只保留最近的一次
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
            "festival_pages": deduped[:20]
        }
    )

    print("[OK] data/processed/festivals.json generated")


if __name__ == "__main__":
    main()
