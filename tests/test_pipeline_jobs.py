from pathlib import Path
import tempfile
import unittest

from backend.app.jobs import PipelineJobStore


class PipelineJobStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = PipelineJobStore(Path(self.temp.name) / "jobs.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_job_progress_logs_and_result_survive_reopen(self):
        job = self.store.create(
            "factory-one",
            "profile",
            message="업로드 대기",
            total_rows=10,
        )
        self.store.start(job["job_id"], "profile", "프로파일링")
        self.store.update(
            job["job_id"],
            current_step="normalize",
            progress=60,
            processed_rows=6,
            message="정규화 6/10",
        )
        completed = self.store.succeed(
            job["job_id"],
            step="complete",
            message="완료",
            result={"upload_id": "u-1"},
            processed_rows=10,
            total_rows=10,
        )
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["result"]["upload_id"], "u-1")
        self.assertGreaterEqual(len(self.store.logs(job["job_id"])), 4)

        reopened = PipelineJobStore(self.store.path)
        self.assertEqual(
            reopened.get(job["job_id"])["result"]["upload_id"], "u-1"
        )

    def test_failed_job_can_retry_and_terminal_job_is_immutable(self):
        job = self.store.create(
            "factory-one", "load", message="적재 대기"
        )
        self.store.start(job["job_id"], "load", "적재 시작")
        failed = self.store.fail(
            job["job_id"], step="load", error="connection lost"
        )
        self.assertEqual(failed["status"], "failed")
        with self.assertRaisesRegex(ValueError, "종료된"):
            self.store.update(job["job_id"], progress=90)

        retry = self.store.retry(job["job_id"])
        self.assertEqual(retry["status"], "queued")
        self.assertEqual(retry["attempt"], 2)
        self.assertEqual(retry["parent_job_id"], job["job_id"])

    def test_queued_job_can_be_cancelled(self):
        job = self.store.create(
            "factory-one", "mapping", message="대기"
        )
        cancelled = self.store.cancel(job["job_id"])
        self.assertEqual(cancelled["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()

