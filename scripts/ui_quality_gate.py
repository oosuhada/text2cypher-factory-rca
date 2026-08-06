#!/usr/bin/env python3
"""Validate enterprise Streamlit RBAC, accessibility and visual contracts."""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from frontend.quality_gate import run_ui_quality_gate


if __name__ == "__main__":
    print(
        json.dumps(
            run_ui_quality_gate(PROJECT_ROOT),
            ensure_ascii=False,
            indent=2,
        )
    )
