from __future__ import annotations

from pathlib import Path

from build_pages import main as build_pages
from common import ROOT, load_json, logger, today_local
from detect_festivals import main as detect_festivals
from fetch_news import main as fetch_news
from fetch_products import main as fetch_products
from process_content import main as process_content


def run_step(name: str, fn) -> None:
    logger.info(f"[START] {name}")
    try:
        fn()
        logger.info(f"[DONE] {name}")
    except Exception:
        logger.exception(f"[FAILED] {name}")
        raise


def validate_outputs() -> None:
    payload_path = ROOT / "data/processed/daily_payload.json"
    index_path = ROOT / "docs/index.html"

    if not payload_path.exists():
        raise RuntimeError("Missing output: data/processed/daily_payload.json")

    if not index_path.exists():
        raise RuntimeError("Missing output: docs/index.html")

    payload = load_json("data/processed/daily_payload.json", {})
    payload_date = payload.get("date")
    expected_date = str(today_local())

    if payload_date != expected_date:
        raise RuntimeError(
            f"Payload date mismatch: expected {expected_date}, got {payload_date}"
        )

    status = payload.get("status", {})
    consumer_count = status.get("consumer_count", 0)
    channel_count = status.get("channel_count", 0)
    product_count = status.get("product_count", 0)

    if consumer_count <= 0 and channel_count <= 0 and product_count <= 0:
        raise RuntimeError("All content sections are empty")

    index_html = index_path.read_text(encoding="utf-8")
    if payload_date not in index_html:
        raise RuntimeError(f"docs/index.html does not contain payload date: {payload_date}")

    logger.info(
        "Validation passed | "
        f"date={payload_date}, consumer={consumer_count}, "
        f"channel={channel_count}, products={product_count}"
    )


def main() -> None:
    logger.info("========== Daily report job started ==========")
    run_step("fetch_news", fetch_news)
    run_step("fetch_products", fetch_products)
    run_step("detect_festivals", detect_festivals)
    run_step("process_content", process_content)
    run_step("build_pages", build_pages)
    run_step("validate_outputs", validate_outputs)
    logger.info("========== Daily report generated successfully ==========")


if __name__ == "__main__":
    main()
