from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "daily_report.log"


def load_yaml(path: str) -> Any:
    with open(ROOT / path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_json(path: str, data: Any) -> None:
    out = ROOT / path
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: str, default: Any = None) -> Any:
    p = ROOT / path
    if not p.exists():
        return default if default is not None else {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("daily_report")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger


logger = setup_logging()


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "and")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_title(text: str) -> str:
    text = normalize_text(text)

    # 去掉常见媒体标题尾巴，增强跨媒体去重
    separators = [" | ", " - ", " — ", " – ", ":"]
    for sep in separators:
        if sep in text:
            left = text.split(sep)[0].strip()
            if len(left) >= 12:
                text = left

    stopwords = {
        "the", "a", "an", "new", "latest", "review", "hands on", "vs",
        "how to", "why", "what", "you", "your", "this", "that",
    }
    tokens = [t for t in text.split() if t not in stopwords]
    return " ".join(tokens[:16]).strip()


def build_dedupe_key(title: str, url: str = "", summary: str = "") -> str:
    ct = canonical_title(title)
    cs = normalize_text(summary)
    summary_part = " ".join(cs.split()[:12])
    return f"{ct} || {summary_part}"


def is_meaningful_text(text: str, min_len: int = 8) -> bool:
    cleaned = normalize_text(text)
    return len(cleaned) >= min_len
