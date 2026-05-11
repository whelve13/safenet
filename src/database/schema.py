# SQL scripts for database initialization

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    total_messages_sent INTEGER DEFAULT 0,
    flagged_messages_count INTEGER DEFAULT 0,
    risk_score REAL DEFAULT 0.0
);
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    receiver_id TEXT,
    content TEXT NOT NULL,
    toxicity_score REAL DEFAULT 0.0,
    is_flagged BOOLEAN DEFAULT 0,
    metadata TEXT,
    FOREIGN KEY(sender_id) REFERENCES users(id)
);
"""

CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    target_user_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    reason TEXT NOT NULL,
    context_message_ids TEXT NOT NULL, -- Stored as comma-separated list
    FOREIGN KEY(target_user_id) REFERENCES users(id)
);
"""

def get_all_schemas() -> list[str]:
    return [CREATE_USERS_TABLE, CREATE_MESSAGES_TABLE, CREATE_ALERTS_TABLE]