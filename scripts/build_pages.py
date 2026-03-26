from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import ROOT, load_json, logger


def main() -> None:
    payload = load_json("data/processed/daily_payload.json", {})

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )

    output_dir = ROOT / "docs"
    output_dir.mkdir(exist_ok=True)

    tpl = env.get_template("index.html.j2")
    html = tpl.render(**payload)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    logger.info("Saved docs/index.html")

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
        output_path = output_dir / f"{f['slug']}.html"
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"Saved docs/{f['slug']}.html")


if __name__ == "__main__":
    main()
