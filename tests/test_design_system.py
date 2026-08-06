import unittest

from frontend.design_system import (
    Action,
    DESIGN_TOKENS,
    INTERNAL_CONSOLE_NAVIGATION,
    NAVIGATION_ITEMS,
    PAGE_BY_LABEL,
    PRODUCT_UI_NAVIGATION,
    REACT_STREAMLIT_BOUNDARY,
    SIDEBAR_SECTION_ORDER,
    SURFACE_OWNERSHIP,
    WIREFLOWS,
    Role,
    ViewState,
    build_global_css,
    can_access,
    can_perform,
    navigation_for_role,
    page_description,
    state_copy,
)


class DesignSystemContractTest(unittest.TestCase):
    def test_sidebar_sections_follow_the_operator_workflow(self):
        self.assertEqual(
            SIDEBAR_SECTION_ORDER,
            (
                "프로젝트",
                "작업공간 이동",
                "대화",
                "실행 설정",
                "역할 미리보기",
                "언어 / Language",
                "안전 설정",
            ),
        )

    def test_information_architecture_has_all_required_workspaces(self):
        self.assertEqual(
            [item.label for item in NAVIGATION_ITEMS],
            [
                "Home",
                "Projects",
                "Data Sources",
                "Pipeline",
                "Query Studio",
                "Graph Explorer",
                "Dashboard",
                "Evaluations",
                "Approval Queue",
                "Audit Logs",
                "Admin",
            ],
        )
        self.assertEqual(len(PAGE_BY_LABEL), len(NAVIGATION_ITEMS))

    def test_role_navigation_enforces_least_privilege(self):
        viewer_pages = {
            item.label for item in navigation_for_role(Role.VIEWER)
        }
        steward_pages = {
            item.label for item in navigation_for_role(Role.DATA_STEWARD)
        }
        admin_pages = {
            item.label for item in navigation_for_role(Role.ADMIN)
        }

        self.assertNotIn("Data Sources", viewer_pages)
        self.assertNotIn("Approval Queue", viewer_pages)
        self.assertIn("Data Sources", steward_pages)
        self.assertIn("Approval Queue", steward_pages)
        self.assertNotIn("Admin", steward_pages)
        self.assertEqual(admin_pages, set(PAGE_BY_LABEL))
        self.assertTrue(can_access(Role.DOMAIN_EXPERT, "Approval Queue"))
        self.assertFalse(can_access(Role.VIEWER, "Admin"))
        self.assertFalse(can_perform(Role.VIEWER, Action.RERUN_QUERY))
        self.assertTrue(can_perform(Role.ADMIN, Action.MANAGE_PLATFORM))

    def test_every_workspace_has_all_four_view_state_contracts(self):
        for item in NAVIGATION_ITEMS:
            copies = {
                state: state_copy(state, page_label=item.label)
                for state in ViewState
            }
            self.assertEqual(set(copies), set(ViewState))
            for copy in copies.values():
                self.assertIn(item.label, copy.message)
                self.assertTrue(copy.title)

    def test_design_tokens_cover_semantics_and_layout(self):
        self.assertTrue(
            {
                "success",
                "warning",
                "error",
                "info",
                "surface",
                "border",
                "text",
            }.issubset(DESIGN_TOKENS["color"])
        )
        self.assertTrue({"type", "space", "radius", "shadow"}.issubset(
            DESIGN_TOKENS
        ))
        css = build_global_css()
        self.assertIn("--p3-success", css)
        self.assertIn(".p3-page-head", css)
        self.assertIn(".p3-state-card", css)
        self.assertIn(".p3-skip-link", css)
        self.assertIn("focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("forced-colors", css)
        self.assertIn("max-width: 760px", css)

    def test_korean_and_english_page_copy_are_available(self):
        self.assertEqual(
            page_description("Dashboard", "ko"),
            PAGE_BY_LABEL["Dashboard"].description,
        )
        self.assertIn("operational", page_description("Dashboard", "en"))

    def test_wireflows_only_reference_declared_workspaces(self):
        declared = set(PAGE_BY_LABEL)
        for flow in WIREFLOWS.values():
            self.assertGreaterEqual(len(flow), 3)
            self.assertTrue(set(flow).issubset(declared))

    def test_react_and_streamlit_have_non_overlapping_product_ownership(self):
        self.assertEqual(
            set(REACT_STREAMLIT_BOUNDARY),
            {"streamlit", "react", "backend"},
        )
        self.assertIn("Query Studio", PRODUCT_UI_NAVIGATION)
        self.assertIn("Evidence / Graph", PRODUCT_UI_NAVIGATION)
        self.assertNotIn("Evaluations", PRODUCT_UI_NAVIGATION)
        self.assertIn("Evaluations", INTERNAL_CONSOLE_NAVIGATION)
        self.assertEqual(SURFACE_OWNERSHIP["rca_query"], "react")
        self.assertEqual(SURFACE_OWNERSHIP["evaluations"], "streamlit")
        self.assertEqual(SURFACE_OWNERSHIP["platform_state"], "backend")
        self.assertTrue(
            any(
                "단일 제품 진입점" in statement
                for statement in REACT_STREAMLIT_BOUNDARY["react"]
            )
        )
        self.assertTrue(
            any(
                "내부 운영 콘솔" in statement
                for statement in REACT_STREAMLIT_BOUNDARY["streamlit"]
            )
        )
        self.assertTrue(
            any(
                "source of truth" in statement
                for statement in REACT_STREAMLIT_BOUNDARY["backend"]
            )
        )


if __name__ == "__main__":
    unittest.main()
