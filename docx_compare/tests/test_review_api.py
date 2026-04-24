from __future__ import annotations

from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from review_api.app import app


class ReviewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.sample_a = Path.cwd() / "samples" / "test_file_a.docx"
        self.sample_b = Path.cwd() / "samples" / "test_file_b.docx"

    def test_review_endpoint_returns_documents_matches_and_downloads(self) -> None:
        with self.sample_a.open("rb") as first_handle, self.sample_b.open(
            "rb"
        ) as second_handle:
            response = self.client.post(
                "/api/review",
                files={
                    "first_file": (
                        self.sample_a.name,
                        first_handle,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                    "second_file": (
                        self.sample_b.name,
                        second_handle,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("reviewId", payload)
        self.assertGreater(payload["summary"]["commonSentenceCount"], 0)
        self.assertTrue(payload["documents"]["first"]["blocks"])
        self.assertTrue(payload["documents"]["second"]["blocks"])
        self.assertTrue(payload["matches"])
        self.assertIn("/api/reviews/", payload["downloads"]["first"])

    def test_sample_review_endpoint_works(self) -> None:
        response = self.client.post("/api/review/sample")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["summary"]["firstFileName"],
            "test_file_a.docx",
        )
        self.assertEqual(
            payload["summary"]["secondFileName"],
            "test_file_b.docx",
        )


if __name__ == "__main__":
    unittest.main()
