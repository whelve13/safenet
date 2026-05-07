from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Message:
    id: str
    timestamp: datetime
    sender_id: str
    content: str
    receiver_id: Optional[str] = None
    toxicity_score: float = 0.0
    is_flagged: bool = False
    
    def __post_init__(self):
        # Basic validation
        if not self.content:
            raise ValueError("Message content cannot be empty")
        if not self.sender_id:
            raise ValueError("Message must have a sender")

    def __str__(self) -> str:
        flag = "[FLAGGED]" if self.is_flagged else ""
        return f"{self.timestamp} | {self.sender_id} -> {self.receiver_id or 'ALL'}: {self.content} {flag}"

    def update_toxicity(self, score: float, threshold: float = 0.7):
        self.toxicity_score = score
        self.is_flagged = score >= threshold
