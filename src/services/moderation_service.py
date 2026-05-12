from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from src.algorithms.toxicity_analyzer import ToxicityAnalyzer
from src.models.config import AnalysisConfig
from src.models.message import Message
from src.models.moderation_event import ModerationEvent


class ModerationService:
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config or AnalysisConfig()
        self.analyzer = ToxicityAnalyzer(self.config)

    @staticmethod
    def _snippet(text: str, max_length: int = 220) -> str:
        normalized = " ".join(text.strip().split())
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max_length - 3] + "..."

    @staticmethod
    def _severity(score: float) -> str:
        if score >= 0.9:
            return "critical"
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _decision(severity: str) -> str:
        if severity == "critical":
            return "block"
        if severity in {"medium", "high"}:
            return "blur"
        return "allow"

    @staticmethod
    def _contributors(metadata: dict) -> list[str]:
        contributors = ["dictionary"]
        if metadata.get("hf_score") is not None:
            contributors.append("toxic-bert")
        return contributors

    @staticmethod
    def _detection_method(metadata: dict) -> str:
        has_hf = metadata.get("hf_score") is not None
        dict_score = float(metadata.get("dict_score", 0.0))
        if not has_hf:
            return "dictionary"
        if dict_score > 0:
            return "hybrid"
        return "toxic-bert"

    @staticmethod
    def _explanation_reason(metadata: dict) -> str:
        dict_score = float(metadata.get("dict_score", 0.0))
        hf_score = metadata.get("hf_score")
        scoring_method = metadata.get("scoring_method", "dictionary")

        if hf_score is None:
            return "Dictionary confidence was sufficient; Toxic-BERT fallback was not used."
        if scoring_method.startswith("huggingface"):
            return "Toxic-BERT fallback increased confidence because dictionary score was below threshold."
        if dict_score > 0:
            return "Dictionary score remained dominant after a Toxic-BERT fallback check."
        return "Toxic-BERT fallback was evaluated but did not increase the final score."

    def _build_result(self, text: str, score: float, metadata: dict) -> dict:
        severity = self._severity(score)
        decision = self._decision(severity)
        explanation_reason = self._explanation_reason(metadata)
        context_adjustment = metadata.get("context_adjustment")
        if context_adjustment:
            explanation_reason = f"{explanation_reason} Context adjustment applied: {context_adjustment}."

        return {
            "snippet": self._snippet(text),
            "toxicity_score": round(float(score), 4),
            "severity": severity,
            "decision": decision,
            "detection_method": self._detection_method(metadata),
            "explanation": {
                "contributors": self._contributors(metadata),
                "scoring_method": metadata.get("scoring_method", "dictionary"),
                "dict_score": round(float(metadata.get("dict_score", 0.0)), 4),
                "hf_score": round(float(metadata["hf_score"]), 4) if metadata.get("hf_score") is not None else None,
                "reason": explanation_reason,
            },
        }

    def analyze_text(self, text: str) -> dict:
        message = Message(
            id=f"MSG-LIVE-{uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc),
            sender_id="live_extension",
            content=text,
        )
        score, metadata = self.analyzer.analyze_message(message)
        return self._build_result(text, score, metadata)

    def analyze_batch(self, texts: list[str]) -> list[dict]:
        messages = [
                Message(
                    id=f"MSG-LIVE-{uuid4().hex[:12]}",
                    timestamp=datetime.now(timezone.utc),
                    sender_id="live_extension",
                    content=text,
                )
            for text in texts
        ]
        results = self.analyzer.analyze_messages_batch(messages)
        return [self._build_result(msg.content, score, metadata) for msg, (score, metadata) in zip(messages, results)]

    @staticmethod
    def should_persist_event(decision: str) -> bool:
        return decision in {"blur", "block"}

    def build_event(
        self,
        analysis_result: dict,
        source: str = "extension",
        page_url: str | None = None,
    ) -> ModerationEvent:
        domain = None
        if page_url:
            parsed = urlparse(page_url)
            domain = parsed.netloc or None

        return ModerationEvent(
            id=f"EVT-{uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc),
            source=source,
            page_url=page_url,
            page_domain=domain,
            snippet=analysis_result["snippet"],
            toxicity_score=float(analysis_result["toxicity_score"]),
            severity=analysis_result["severity"],
            decision=analysis_result["decision"],
            detection_method=analysis_result["detection_method"],
            explanation=analysis_result["explanation"]["reason"],
        )

