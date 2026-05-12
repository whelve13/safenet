from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ModerationEvent:
    id: str
    timestamp: datetime
    source: str
    snippet: str
    toxicity_score: float
    severity: str
    decision: str
    detection_method: str
    explanation: str
    page_url: Optional[str] = None
    page_domain: Optional[str] = None

