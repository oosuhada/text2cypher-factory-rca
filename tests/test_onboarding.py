from datetime import datetime, timedelta, timezone
import unittest

from frontend.onboarding import (
    format_elapsed,
    job_elapsed_seconds,
    onboarding_progress,
    profile_quality_warnings,
)


class OnboardingPresentationTest(unittest.TestCase):
    def test_lifecycle_progress_never_marks_future_steps_complete(self):
        progress = onboarding_progress("mapping_review")
        self.assertEqual(progress["current"], "mapping")
        self.assertEqual(
            [step["state"] for step in progress["steps"]],
            [
                "complete",
                "complete",
                "complete",
                "active",
                "pending",
                "pending",
                "pending",
                "pending",
            ],
        )

    def test_quality_warnings_report_missing_identity_and_high_null_rate(self):
        warnings = profile_quality_warnings(
            {
                "files": [
                    {
                        "filename": "events.csv",
                        "row_count": 10,
                        "columns": [
                            {
                                "name": "value",
                                "identity_candidate": False,
                                "missing_count": 4,
                            }
                        ],
                    }
                ]
            }
        )
        self.assertEqual(len(warnings), 2)
        self.assertIn("고유 ID 후보", warnings[0])
        self.assertIn("결측 4/10", warnings[1])

    def test_elapsed_time_is_stable_after_terminal_timestamp(self):
        started = datetime(2026, 7, 28, tzinfo=timezone.utc)
        job = {
            "started_at": started.isoformat(),
            "finished_at": (started + timedelta(seconds=125)).isoformat(),
        }
        self.assertEqual(job_elapsed_seconds(job), 125)
        self.assertEqual(format_elapsed(125), "2분 5초")


if __name__ == "__main__":
    unittest.main()
