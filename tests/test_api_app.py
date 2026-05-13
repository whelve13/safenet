import os
import tempfile
import time
import unittest

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src.api import app as api_app
from src.database.repository import DatabaseRepository
from src.models.config import AnalysisConfig
from src.services.moderation_service import ModerationService


class TestSafeNetApi(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            self.db_path = tmp_db.name

        self.repo = DatabaseRepository(self.db_path)
        api_app.repo = self.repo
        api_app.moderation_service = ModerationService(AnalysisConfig(use_hf_model=False))
        self.client = TestClient(api_app.app)

    def tearDown(self):
        for _ in range(10):
            try:
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                return
            except PermissionError:
                time.sleep(0.1)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_text_analysis_persists_block_event(self):
        response = self.client.post(
            "/v1/analyze/text",
            json={
                "text": "kys",
                "source": "extension",
                "page_url": "https://example.com/post/1",
                "persist_event_on_action": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["decision"], "block")
        self.assertTrue(payload["persisted_event"])

        events = self.repo.get_moderation_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][2], "extension")

    def test_text_analysis_does_not_persist_allow_event(self):
        response = self.client.post(
            "/v1/analyze/text",
            json={
                "text": "hello world",
                "source": "extension",
                "persist_event_on_action": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["decision"], "allow")
        self.assertFalse(payload["persisted_event"])
        self.assertEqual(len(self.repo.get_moderation_events()), 0)

    def test_text_analysis_dedupes_same_event_in_window(self):
        payload = {
            "text": "kys",
            "source": "extension",
            "page_url": "https://example.com/post/1",
            "persist_event_on_action": True,
        }
        first = self.client.post("/v1/analyze/text", json=payload)
        second = self.client.post("/v1/analyze/text", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.json()["persisted_event"])
        self.assertFalse(second.json()["persisted_event"])
        self.assertEqual(len(self.repo.get_moderation_events()), 1)


if __name__ == "__main__":
    unittest.main()

