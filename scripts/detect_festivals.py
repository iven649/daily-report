from __future__ import annotations
from datetime import date, timedelta
from dateutil.easter import easter
from common import load_yaml, dump_json

def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d

def resolve_date(item: dict, year: int) -> date:
    rule = item["rule"]
    if rule == "fixed":
        return date(year, item["month"], item["day"])
    if rule == "easter":
        return easter(year)
    if rule == "nth_weekday":
        if item.get("nth_from_end") == 1:
            return last_weekday_of_month(year, item["month"], item["weekday"])
    raise ValueError(f"Unsupported rule: {rule}")

def main():
    today = date.today()
    conf = load_yaml("config/festivals.yaml")
    content = load_yaml("config/festival_content.yaml")["content"]

    resolved = []
    for item in conf["festivals"]:
        d = resolve_date(item, today.year)
        if d < today:
            d = resolve_date(item, today.year + 1)
        days = (d - today).days
        x = dict(item)
        x["date"] = d.isoformat()
        x["countdown"] = days
        x["year"] = d.year
        x.update(content.get(item["slug"], {}))
        resolved.append(x)

    resolved.sort(key=lambda x: x["countdown"])

    cn = [x for x in resolved if x["market"] == "CN" and 0 <= x["countdown"] <= 45][:1]
    us = [x for x in resolved if x["market"] == "US" and 0 <= x["countdown"] <= 45][:1]
    homepage = cn + us

    dump_json("data/processed/festivals.json", {
        "today": today.isoformat(),
        "festival_cards": homepage,
        "festival_pages": homepage
    })
    print("[OK] data/processed/festivals.json")

if __name__ == "__main__":
    main()
