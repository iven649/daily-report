from __future__ import annotations
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from common import ROOT, load_json

def main():
    payload = load_json("data/processed/daily_payload.json", {})
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "xml"])
    )

    dist = ROOT / "docs"
    dist.mkdir(exist_ok=True)

    tpl = env.get_template("index.html.j2")
    html = tpl.render(**payload)
    (dist / "index.html").write_text(html, encoding="utf-8")

    festival_tpl = env.get_template("festival.html.j2")
    for f in payload.get("festival_pages", []):
        d = datetime.fromisoformat(f["date"]).date()
        html = festival_tpl.render(
            name=f["name"],
            icon=f.get("icon", "🎉"),
            year=d.year,
            date_text=d.strftime("%Y-%m-%d"),
            countdown=f["countdown"],
            origin=f.get("origin", ""),
            story=f.get("story", ""),
            customs=f.get("customs", []),
            consumption=f.get("consumption", []),
            holiday=f.get("holiday", ""),
        )
        (dist / f"{f['slug']}.html").write_text(html, encoding="utf-8")

    print("[OK] dist/index.html")
    for f in payload.get("festival_pages", []):
        print(f"[OK] dist/{f['slug']}.html")

if __name__ == "__main__":
    main()
