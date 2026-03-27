from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "daily_report.log"

DEFAULT_TIMEZONE = "Asia/Shanghai"
LOCAL_TZ = ZoneInfo(DEFAULT_TIMEZONE)


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


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return now_utc().astimezone(LOCAL_TZ)


def today_local() -> date:
    return now_local().date()


def format_local_timestamp(fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    return now_local().strftime(fmt)


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "and")
    text = text.replace("’", "'")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff' ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_title(text: str) -> str:
    text = normalize_text(text)
    stopwords = {
        "the", "a", "an", "new", "latest", "review", "hands", "on", "vs",
        "how", "to", "why", "what", "you", "your", "this", "that",
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


def parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        candidate = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def hours_since(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    delta = now_utc() - dt
    return delta.total_seconds() / 3600


def freshness_label(hours: Optional[float]) -> str:
    if hours is None:
        return "时间未知"
    if hours <= 24:
        return "24h内"
    if hours <= 72:
        return "近3天"
    if hours <= 168:
        return "近7天"
    return "较早内容"
