from datetime import datetime, timezone
import hashlib
import re
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
        if metadata.get("hf_score") is None:
            return ["dictionary"]
        contributors = ["toxic-bert"]
        if float(metadata.get("weighted_dict_score") or metadata.get("dict_score", 0.0)) > 0:
            contributors.insert(0, "dictionary")
        return contributors

    @staticmethod
    def _detection_method(metadata: dict) -> str:
        hf_score = metadata.get("hf_score")
        if hf_score is None:
            return "dictionary"

        weighted_dict = float(metadata.get("weighted_dict_score") or metadata.get("dict_score", 0.0))
        hf_contribution = float(metadata.get("hf_adjusted_score") or hf_score or 0.0)

        if weighted_dict > 0 and hf_contribution > 0:
            return "hybrid"
        if hf_contribution > 0:
            return "toxic-bert"
        return "hybrid" if weighted_dict > 0 else "toxic-bert"

    @staticmethod
    def _explanation_reason(metadata: dict) -> str:
        if metadata.get("hf_score") is None:
            return "Toxic-BERT was unavailable, so SafeNet used dictionary scoring only."
        if metadata.get("scoring_mode") == "hybrid_model_priority":
            return (
                "Hybrid model-priority mode used. Final score = max(hf_score, dictionary_score * 0.85). "
                "Toxic-BERT is the primary contextual validator."
            )
        return "Legacy dictionary-first fallback mode used (HF evaluated only under the fallback threshold)."

    def _build_result(self, text: str, score: float, metadata: dict) -> dict:
        severity = self._severity(score)
        decision = self._decision(severity)
        explanation_reason = self._explanation_reason(metadata)
        context_adjustment = metadata.get("context_adjustment")
        if context_adjustment:
            explanation_reason = f"{explanation_reason} Context adjustment applied: {context_adjustment}."
        weighted_dict_score = metadata.get("weighted_dict_score")
        if weighted_dict_score is None:
            weighted_dict_score = metadata.get("dict_score", 0.0)

        return {
            "snippet": self._snippet(text),
            "toxicity_score": round(float(score), 4),
            "severity": severity,
            "decision": decision,
            "detection_method": self._detection_method(metadata),
            "explanation": {
                "contributors": self._contributors(metadata),
                "scoring_mode": metadata.get("scoring_mode", "hybrid_model_priority"),
                "scoring_method": metadata.get("scoring_method", "dictionary"),
                "dict_score": round(float(metadata.get("dict_score", 0.0)), 4),
                "dictionary_weighted_score": round(float(weighted_dict_score), 4),
                "dictionary_severity_signal": metadata.get("dictionary_severity_signal", "low"),
                "matched_terms": metadata.get("matched_terms", []),
                "matched_phrases": metadata.get("matched_phrases", []),
                "matched_term_spans": metadata.get("matched_term_spans", []),
                "matched_phrase_spans": metadata.get("matched_phrase_spans", []),
                "hf_score": round(float(metadata["hf_score"]), 4) if metadata.get("hf_score") is not None else None,
                "hf_adjusted_score": (
                    round(float(metadata["hf_adjusted_score"]), 4)
                    if metadata.get("hf_adjusted_score") is not None
                    else None
                ),
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

    @staticmethod
    def _normalize_for_dedupe(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    @classmethod
    def _build_event_hash(cls, domain: str | None, snippet: str, decision: str) -> str:
        normalized_domain = (domain or "unknown").strip().lower()
        normalized_snippet = cls._normalize_for_dedupe(snippet)
        payload = f"{normalized_domain}|{normalized_snippet}|{decision.strip().lower()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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

        snippet = analysis_result["snippet"]
        decision = analysis_result["decision"]
        event_hash = self._build_event_hash(domain, snippet, decision)

        return ModerationEvent(
            id=f"EVT-{uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc),
            source=source,
            page_url=page_url,
            page_domain=domain,
            snippet=snippet,
            toxicity_score=float(analysis_result["toxicity_score"]),
            severity=analysis_result["severity"],
            decision=decision,
            detection_method=analysis_result["detection_method"],
            explanation=analysis_result["explanation"]["reason"],
            event_hash=event_hash,
        )

