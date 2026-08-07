from __future__ import annotations

import unittest
from unittest.mock import patch

from frontend import legacy_page_redirect


class StreamlitLegacyRedirectTest(unittest.TestCase):
    def test_legacy_url_preserves_project_context(self):
        self.assertEqual(
            legacy_page_redirect.legacy_workspace_url(
                "data_sources", "equipment-history"
            ),
            "/?workspace=data_sources&project_id=equipment-history",
        )

    def test_legacy_url_without_project_uses_workspace_only(self):
        self.assertEqual(
            legacy_page_redirect.legacy_workspace_url("projects"),
            "/?workspace=projects",
        )

    def test_legacy_page_renders_a_non_blank_migration_notice(self):
        with (
            patch.object(
                legacy_page_redirect.st,
                "query_params",
                {"project_id": "equipment-history"},
            ),
            patch.object(legacy_page_redirect.st, "set_page_config"),
            patch.object(legacy_page_redirect.st, "title") as title,
            patch.object(legacy_page_redirect.st, "write") as write,
            patch.object(legacy_page_redirect.st, "markdown") as markdown,
            patch.object(legacy_page_redirect.st, "caption") as caption,
        ):
            legacy_page_redirect.redirect_legacy_page("data_sources")

        title.assert_called_once_with("내부 콘솔 주소가 변경되었습니다.")
        self.assertIn("이전 Streamlit 자동 페이지", write.call_args.args[0])
        self.assertIn(
            "/?workspace=data_sources&amp;project_id=equipment-history",
            markdown.call_args.args[0],
        )
        caption.assert_called_once_with(
            "새 주소: /?workspace=data_sources&project_id=equipment-history"
        )


if __name__ == "__main__":
    unittest.main()
