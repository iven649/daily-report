from __future__ import annotations

from fetch_news import main as fetch_news
from fetch_products import main as fetch_products
from detect_festivals import main as detect_festivals
from process_content import main as process_content
from build_pages import main as build_pages

from common import logger


def run_step(name: str, fn) -> None:
    logger.info(f"[START] {name}")
    try:
        fn()
        logger.info(f"[DONE] {name}")
    except Exception:
        logger.exception(f"[FAILED] {name}")
        raise


def main() -> None:
    logger.info("========== Daily report job started ==========")

    run_step("fetch_news", fetch_news)
    run_step("fetch_products", fetch_products)
    run_step("detect_festivals", detect_festivals)
    run_step("process_content", process_content)
    run_step("build_pages", build_pages)

    logger.info("========== Daily report generated successfully ==========")


if __name__ == "__main__":
    main()
