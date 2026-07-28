from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from frontend.design_system import Role
from frontend.ui_mode import (
    DEPLOYMENT_FORBIDDEN_COPY,
    UiMode,
    configured_role,
    current_ui_mode,
    runtime_provider_and_model,
    visible_workspace_labels,
)


class UiModeContractTest(unittest.TestCase):
    def test_default_mode_is_demo(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(current_ui_mode(), UiMode.DEMO)

    def test_invalid_mode_is_rejected(self):
        with patch.dict(os.environ, {"P3_UI_MODE": "preview"}, clear=True):
            with self.assertRaises(ValueError):
                current_ui_mode()

    def test_demo_hides_foundation_workspaces_and_uses_fixed_role(self):
        labels = ("Projects", "Approval Queue", "Admin")
        with patch.dict(os.environ, {"P3_UI_MODE": "demo"}, clear=True):
            self.assertEqual(visible_workspace_labels(labels), ("Projects",))
            self.assertEqual(configured_role(), Role.DATA_STEWARD)

    def test_development_keeps_internal_controls(self):
        labels = ("Projects", "Approval Queue", "Admin")
        with patch.dict(
            os.environ,
            {"P3_UI_MODE": "development"},
            clear=True,
        ):
            self.assertEqual(visible_workspace_labels(labels), labels)
            self.assertEqual(configured_role(), Role.ADMIN)

    def test_provider_and_model_are_server_managed(self):
        with patch.dict(
            os.environ,
            {"P3_API_PROVIDER": "gemini", "P3_API_MODEL": "model-x"},
            clear=True,
        ):
            self.assertEqual(runtime_provider_and_model(), ("gemini", "model-x"))

    def test_demo_streamlit_dom_has_no_deployment_forbidden_copy(self):
        from streamlit.testing.v1 import AppTest

        app_path = Path(__file__).resolve().parents[1] / "frontend" / "streamlit_app.py"
        with patch.dict(os.environ, {"P3_UI_MODE": "demo"}, clear=False):
            app = AppTest.from_file(str(app_path)).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        rendered = "\n".join(
            [
                markdown.value
                for markdown in app.markdown
                if not markdown.value.lstrip().startswith("<style")
            ]
            + [caption.value for caption in app.caption]
            + [info.value for info in app.info]
            + [box.label for box in app.selectbox]
            + [radio.label for radio in app.radio]
        )
        for forbidden in DEPLOYMENT_FORBIDDEN_COPY:
            self.assertNotIn(forbidden, rendered)
        navigation = next(radio for radio in app.radio if radio.label == "Navigation")
        self.assertNotIn("Approval Queue", navigation.options)
        self.assertNotIn("Admin", navigation.options)


if __name__ == "__main__":
    unittest.main()
