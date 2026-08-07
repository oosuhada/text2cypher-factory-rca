"""P3 manufacturing knowledge-graph RCA Streamlit application."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.app_shell import render_app_shell
from frontend.streamlit_router import build_hidden_navigation


APP_TITLE = "Factory Graph RCA — Internal Console"


def main() -> None:
    render_app_shell(APP_TITLE)
    navigation = build_hidden_navigation()
    navigation.run()


if __name__ == "__main__":
    main()
