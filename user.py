from dataclasses import dataclass, field
from typing import Set

@dataclass
class User:
    id: str
    username: str
    total_messages_sent: int = 0
    flagged_messages_count: int = 0
    risk_score: float = 0.0
    victims: Set[str] = field(default_factory=set)

    def increment_messages(self, is_flagged: bool = False):
        self.total_messages_sent += 1
        if is_flagged:
            self.flagged_messages_count += 1

    def add_victim(self, victim_id: str):
        self.victims.add(victim_id)

    def update_risk_score(self, new_score: float):
        self.risk_score = new_score

    def get_toxicity_ratio(self) -> float:
        if self.total_messages_sent == 0:
            return 0.0
        return self.flagged_messages_count / self.total_messages_sent

    def __str__(self) -> str:
        return f"User({self.username}, Risk: {self.risk_score:.2f}, Flagged: {self.flagged_messages_count}/{self.total_messages_sent})"