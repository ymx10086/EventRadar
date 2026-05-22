#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Persistent automation run history.

Uses JSON Lines so writes are append-only and easy to inspect or tail on small
self-hosted deployments.
"""

import json
import os
from pathlib import Path
from typing import Dict, List

DEFAULT_HISTORY_DIR = Path(__file__).parent.parent / "data" / "automation"
HISTORY_DIR = Path(os.getenv("AUTOMATION_HISTORY_DIR", str(DEFAULT_HISTORY_DIR)))
HISTORY_FILE = HISTORY_DIR / "runs.jsonl"


def append_run(record: Dict):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def list_runs(limit: int = 30) -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    runs = []
    for line in reversed(lines[-max(limit * 3, limit):]):
        if len(runs) >= limit:
            break
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs
