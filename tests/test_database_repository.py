import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.repository import DatabaseRepository
from src.models.message import Message
from src.models.moderation_event import ModerationEvent


class TestDatabaseRepositoryMigrations(unittest.TestCase):
    def test_adds_metadata_column_for_legacy_messages_table(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            db_path = tmp_db.name

        def cleanup_db():
            for _ in range(10):
                try:
                    if os.path.exists(db_path):
                        os.remove(db_path)
                    return
                except PermissionError:
                    time.sleep(0.1)

        self.addCleanup(cleanup_db)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    receiver_id TEXT,
                    content TEXT NOT NULL,
                    toxicity_score REAL DEFAULT 0.0,
                    is_flagged BOOLEAN DEFAULT 0
                );
            """)
            conn.commit()

        repo = DatabaseRepository(db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            columns = [row[1] for row in cursor.execute("PRAGMA table_info(messages)").fetchall()]
            self.assertIn("metadata", columns)

        message = Message(
            id="msg-legacy-1",
            timestamp=datetime.now(),
            sender_id="user_1",
            receiver_id="user_2",
            content="hello",
        )
        setattr(message, "scoring_metadata", {"scoring_method": "dictionary", "dict_score": 0.2})
        repo.save_message(message)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            metadata = cursor.execute(
                "SELECT metadata FROM messages WHERE id = ?", (message.id,)
            ).fetchone()[0]
            self.assertIn("scoring_method", metadata)

    def test_save_and_read_moderation_event(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            db_path = tmp_db.name

        def cleanup_db():
            for _ in range(10):
                try:
                    if os.path.exists(db_path):
                        os.remove(db_path)
                    return
                except PermissionError:
                    time.sleep(0.1)

        self.addCleanup(cleanup_db)

        repo = DatabaseRepository(db_path)
        event = ModerationEvent(
            id="EVT-1",
            timestamp=datetime.now(),
            source="extension",
            page_url="https://example.com/chat",
            page_domain="example.com",
            snippet="you are worthless",
            toxicity_score=0.91,
            severity="critical",
            decision="block",
            detection_method="hybrid",
            explanation="Toxic-BERT fallback increased confidence because dictionary score was below threshold.",
        )
        repo.save_moderation_event(event)

        rows = repo.get_moderation_events(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "extension")
        self.assertEqual(rows[0][8], "block")


if __name__ == "__main__":
    unittest.main()
