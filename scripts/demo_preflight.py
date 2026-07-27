#!/usr/bin/env python3
"""Check every local dependency required by the stage-17 demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.diagnostics import (
    collect_demo_diagnostics,
    diagnostics_pass,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = collect_demo_diagnostics(PROJECT_ROOT)
    if args.json:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
    else:
        for check in checks:
            print(
                f"[{check['status']:<8}] {check['check']}: "
                f"{check['detail']}"
            )
    if not diagnostics_pass(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
