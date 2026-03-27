from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from common import ROOT, load_json, logger


def write_if_changed(path: Path, content: str) -> bool:
    old_content = path.read_text(encoding="utf-8") if path.exists() else None
    if old_content == content:
        logger.info(f"No visible change for {path.relative_to(ROOT)}")
        return False

    path.write_text(content, encoding="utf-8")
    digest = hashlib.md5(content.encode("utf-8")).hexdigest()[:10]
    logger.info(f"Saved {path.relative_to(ROOT)} | md5={digest}")
    return True


def main() -> None:
    payload = load_json("data/processed/daily_payload.json", {})

    if not payload:
        raise RuntimeError("data/processed/daily_payload.json is missing or empty")

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )

    output_dir = ROOT / "docs"
    output_dir.mkdir(exist_ok=True)

    changed_files = 0

    tpl = env.get_template("index.html.j2")
    html = tpl.render(**payload)
    if write_if_changed(output_dir / "index.html", html):
        changed_files += 1

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
        if write_if_changed(output_path, html):
            changed_files += 1

    logger.info(f"Page build finished | changed_files={changed_files}")
