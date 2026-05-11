import sqlite3
import csv
import io
import sys
import os
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.database.schema import get_all_schemas
from src.models.user import User
from src.models.message import Message
from src.models.alert import Alert, AlertSeverity
from datetime import datetime


class DatabaseRepository:
    # handles all SQLite database operations for persisting and retrieving SafeNet data.
    def __init__(self, db_path: str = "safenet.db"):
        self.db_path = db_path
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for schema in get_all_schemas():
                cursor.execute(schema)
            self._run_migrations(cursor)
            conn.commit()

    def _run_migrations(self, cursor: sqlite3.Cursor):
        # keep existing databases compatible when new columns are introduced
        cursor.execute("PRAGMA table_info(messages)")
        message_columns = {row[1] for row in cursor.fetchall()}
        if "metadata" not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN metadata TEXT")

    def clear_all_data(self):
        # wipes all tables for a fresh analysis run
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alerts")
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM users")
            conn.commit()

    # ── Core save operations ────────────────────────────────────────────────

    def save_user(self, user: User):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users (id, username, total_messages_sent, flagged_messages_count, risk_score)
                VALUES (?, ?, ?, ?, ?)
            """, (user.id, user.username, user.total_messages_sent, user.flagged_messages_count, user.risk_score))
            conn.commit()

    def save_message(self, message: Message):
        with self._get_connection() as conn:
            import json
            cursor = conn.cursor()
            metadata_str = json.dumps(getattr(message, "scoring_metadata", {}))
            cursor.execute("""
                INSERT OR IGNORE INTO messages (id, timestamp, sender_id, receiver_id, content, toxicity_score, is_flagged, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.id, message.timestamp.isoformat(), message.sender_id,
                message.receiver_id, message.content, message.toxicity_score, message.is_flagged, metadata_str
            ))
            conn.commit()

    def save_alert(self, alert: Alert):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            context_str = ",".join(alert.context_message_ids)
            cursor.execute("""
                INSERT OR IGNORE INTO alerts (id, timestamp, target_user_id, severity, reason, context_message_ids)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.id, alert.timestamp.isoformat(), alert.target_user_id,
                alert.severity.value, alert.reason, context_str
            ))
            conn.commit()

    # ── Dashboard queries ───────────────────────────────────────────────────

    def get_all_alerts(self) -> list[tuple]:
        # returns all alerts joined with user data
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.timestamp, a.target_user_id, u.username, a.severity, a.reason
                FROM alerts a
                JOIN users u ON a.target_user_id = u.id
                ORDER BY a.timestamp DESC
            """)
            return cursor.fetchall()

    def get_top_risky_users(self, limit: int = 10) -> list[tuple]:
        # returns top risky users
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, risk_score, flagged_messages_count, total_messages_sent
                FROM users
                WHERE risk_score > 0
                ORDER BY risk_score DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()

    def get_summary_stats(self) -> dict:
        # returns aggregate statistics for the overview cards
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_msgs = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM messages WHERE is_flagged = 1")
            flagged_msgs = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM alerts")
            total_alerts = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE severity = 'CRITICAL'")
            critical_alerts = cursor.fetchone()[0]
            return {
                "total_messages": total_msgs,
                "flagged_messages": flagged_msgs,
                "total_users": total_users,
                "total_alerts": total_alerts,
                "critical_alerts": critical_alerts,
            }

    def get_flagged_interactions(self) -> list[tuple]:
        # returns sender/receiver pairs from flagged messages for graph building
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sender_id, receiver_id, toxicity_score
                FROM messages
                WHERE is_flagged = 1 AND receiver_id IS NOT NULL
            """)
            return cursor.fetchall()

    def get_victim_summary(self) -> list[tuple]:
        # returns users who are targets of flagged messages
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.receiver_id,
                       COALESCE(u.username, m.receiver_id) AS victim_name,
                       COUNT(*) AS times_targeted,
                       COUNT(DISTINCT m.sender_id) AS distinct_aggressors
                FROM messages m
                LEFT JOIN users u ON m.receiver_id = u.id
                WHERE m.is_flagged = 1 AND m.receiver_id IS NOT NULL
                GROUP BY m.receiver_id
                ORDER BY times_targeted DESC
            """)
            return cursor.fetchall()

    def get_messages_targeting_user(self, victim_id: str) -> list[tuple]:
        # returns all flagged messages directed at a specific user
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.timestamp, m.sender_id, m.content, m.toxicity_score, m.metadata
                FROM messages m
                WHERE m.receiver_id = ? AND m.is_flagged = 1
                ORDER BY m.timestamp ASC
            """, (victim_id,))
            return cursor.fetchall()

    def get_conversation_context(self, msg_timestamp: str, window: int = 3) -> list[tuple]:
        # returns messages around a specific timestamp for context
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, sender_id, receiver_id, content, toxicity_score, is_flagged
                FROM messages
                ORDER BY timestamp ASC
            """)
            all_msgs = cursor.fetchall()

        # find index of target timestamp
        target_idx = None
        for i, m in enumerate(all_msgs):
            if m[0] == msg_timestamp:
                target_idx = i
                break
        if target_idx is None:
            return []

        start = max(0, target_idx - window)
        end = min(len(all_msgs), target_idx + window + 1)
        return all_msgs[start:end]

    def get_alerts_csv_bytes(self) -> bytes:
        # generates an in-memory CSV of alerts for download
        alerts = self.get_all_alerts()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Alert ID", "Timestamp", "User ID", "Username", "Severity", "Reason"])
        for alert in alerts:
            writer.writerow(alert)
        return output.getvalue().encode('utf-8')

    def has_data(self) -> bool:
        # checks if there is any data at all
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            return cursor.fetchone()[0] > 0
