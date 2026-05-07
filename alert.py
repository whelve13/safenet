from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class AlertSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class Alert:
    id: str
    timestamp: datetime
    target_user_id: str
    severity: AlertSeverity
    reason: str
    context_message_ids: list[str]

    def __post_init__(self):
        if not self.reason:
            raise ValueError("Alert must have a stated reason.")
        if not self.context_message_ids:
            self.context_message_ids = []

    def __str__(self) -> str:
        return f"[{self.severity.value}] Alert for User {self.target_user_id}: {self.reason} ({len(self.context_message_ids)} msgs)"
