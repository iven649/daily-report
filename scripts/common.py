from __future__ import annotations
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(path: str):
    with open(ROOT / path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def dump_json(path: str, data):
    out = ROOT / path
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path: str, default=None):
    p = ROOT / path
    if not p.exists():
        return default if default is not None else {}
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)
