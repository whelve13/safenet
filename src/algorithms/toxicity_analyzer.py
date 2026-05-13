import re
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.message import Message
from src.models.config import AnalysisConfig
from src.structures.trie import Trie
from src.algorithms.hf_toxicity_model import HFToxicityModel

# default vocabulary built into the system
DEFAULT_TOXIC_WORDS: dict[str, float] = {
    "idiot": 0.5,
    "stupid": 0.4,
    "loser": 0.6,
    "ugly": 0.5,
    "die": 1.0,
    "kill": 1.0,
    "hate": 0.7,
    "dumb": 0.4,
    "trash": 0.6,
    "freak": 0.5,
    "moron": 0.5,
    "pathetic": 0.6,
    "retard": 0.9,
    "worthless": 0.8,
    "disgusting": 0.6,
    "useless": 0.5,
    "scum": 0.7,
    "creep": 0.5,
    "weirdo": 0.4,
    "clown": 0.4,
    "fool": 0.4,
    "trash": 0.6,
    "garbage": 0.6,
    "worthless": 0.8,
    "useless": 0.6,
    "pathetic": 0.6,
    "failure": 0.6,
    "degenerate": 0.7,
}

DEFAULT_TOXIC_PHRASES: dict[str, float] = {
    "kill yourself": 1.0,
    "nobody likes you": 0.8,
    "you are worthless": 0.9,
    "drink bleach": 1.0,
    "go die": 1.0,
    "kys": 1.0,
    "end yourself": 1.0,
    "no one cares": 0.6,
    "shut up": 0.3,
    "nobody likes you": 0.8,
    "no one likes you": 0.8,
    "nobody wants you": 0.9,
    "everyone hates you": 0.9,
    "you have no friends": 0.7,
    "you do not belong here": 0.7,
    "get out of here": 0.5,
    "go away": 0.4,
    "you are useless": 0.8,
    "you are worthless": 0.9,
    "you are pathetic": 0.8,
    "you are disgusting": 0.8,
    "you are a loser": 0.7,
    "you are trash": 0.8,
    "you are garbage": 0.8,
    "kill yourself": 1.0,
    "kys": 1.0,
    "go die": 1.0,
    "end yourself": 1.0,
    "drink bleach": 1.0,
    "nobody cares if you die": 1.0,
    "the world is better without you": 1.0,
    "shut up": 0.3,
    "shut the hell up": 0.6,
    "stop talking": 0.3,
    "delete your account": 0.5,
    "leave the internet": 0.6,
}

POSITIVE_PROFANITY_IDIOM_PATTERN = re.compile(
    r"\b(?:fucking|fuckin)\s+(?:awesome|amazing|great|fantastic|brilliant|epic|cool)\b"
)

SCORING_MODE_HYBRID_MODEL_PRIORITY = "hybrid_model_priority"
SCORING_MODE_DICTIONARY_FIRST_FALLBACK = "dictionary_first_fallback"


class ToxicityAnalyzer:
    # analyzes message content to determine toxicity
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config or AnalysisConfig()
        self.abusive_trie = Trie()
        self.abusive_phrases: dict[str, float] = {}

        self._load_vocabulary()
        self.hf_model = HFToxicityModel(self.config)

    def _load_vocabulary(self):
        # built-in words
        for word, weight in DEFAULT_TOXIC_WORDS.items():
            self.abusive_trie.insert(word, weight)

        # user-defined custom words from config
        for word, weight in self.config.custom_toxic_words.items():
            self.abusive_trie.insert(word.lower(), weight)

        # built-in phrases
        self.abusive_phrases = dict(DEFAULT_TOXIC_PHRASES)

        # user-defined custom phrases from config
        for phrase, weight in self.config.custom_toxic_phrases.items():
            self.abusive_phrases[phrase.lower()] = weight

    @staticmethod
    def _severity_signal(score: float) -> str:
        if score >= 0.9:
            return "critical"
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _phrase_tokens(phrase: str) -> list[str]:
        return re.findall(r"\w+", str(phrase).lower())

    def _build_phrase_regex(self, phrase: str):
        tokens = self._phrase_tokens(phrase)
        if not tokens:
            return None

        token_patterns = [rf"\b{re.escape(token)}\b" for token in tokens]
        if len(token_patterns) == 1:
            pattern = token_patterns[0]
        else:
            pattern = r"(?:[\W_]+)".join(token_patterns)

        return re.compile(pattern, re.IGNORECASE | re.UNICODE)

    def _dictionary_scan(self, text: str) -> dict:
        score = 0.0
        raw_text = str(text)
        matched_terms: list[str] = []
        matched_phrases: list[str] = []
        matched_term_spans: list[dict] = []
        matched_phrase_spans: list[dict] = []
        seen_terms: set[str] = set()
        seen_phrases: set[str] = set()

        for word_match in re.finditer(r"\b\w+\b", raw_text, flags=re.UNICODE):
            word = word_match.group(0).lower()
            found, weight = self.abusive_trie.search(word)
            if found:
                score += weight
                matched_term_spans.append(
                    {
                        "start": word_match.start(),
                        "end": word_match.end(),
                        "term": word,
                    }
                )
                if word not in seen_terms:
                    matched_terms.append(word)
                    seen_terms.add(word)

        for phrase, weight in self.abusive_phrases.items():
            phrase_regex = self._build_phrase_regex(phrase)
            if phrase_regex is None:
                continue

            phrase_matches = list(phrase_regex.finditer(raw_text))
            if not phrase_matches:
                continue

            score += weight * len(phrase_matches)
            normalized_phrase = " ".join(self._phrase_tokens(phrase))
            if normalized_phrase not in seen_phrases:
                matched_phrases.append(normalized_phrase)
                seen_phrases.add(normalized_phrase)

            for phrase_match in phrase_matches:
                matched_phrase_spans.append(
                    {
                        "start": phrase_match.start(),
                        "end": phrase_match.end(),
                        "phrase": normalized_phrase,
                    }
                )

        dict_score = min(score, 1.0)
        return {
            "dict_score": dict_score,
            "matched_terms": matched_terms,
            "matched_phrases": matched_phrases,
            "matched_term_spans": matched_term_spans,
            "matched_phrase_spans": matched_phrase_spans,
            "dictionary_severity_signal": self._severity_signal(dict_score),
        }

    def _apply_hf_context_guard(self, text: str, dict_score: float, hf_score: float) -> tuple[float, str | None]:
        # keep HF from over-penalizing positive idiomatic profanity when dictionary is clean
        if not self.config.hf_context_guard_enabled:
            return hf_score, None
        if dict_score > 0:
            return hf_score, None
        if hf_score < self.config.hf_context_guard_min_hf_score:
            return hf_score, None

        normalized = text.lower()
        if POSITIVE_PROFANITY_IDIOM_PATTERN.search(normalized):
            return min(hf_score, self.config.hf_positive_idiom_cap), "positive_profanity_idiom"

        return hf_score, None

    def _resolve_scoring_mode(self) -> str:
        mode = (self.config.scoring_mode or "").strip().lower()
        if mode in {SCORING_MODE_HYBRID_MODEL_PRIORITY, SCORING_MODE_DICTIONARY_FIRST_FALLBACK}:
            return mode
        return SCORING_MODE_HYBRID_MODEL_PRIORITY

    def _hf_available(self) -> bool:
        return self.config.use_hf_model and self.hf_model.is_loaded

    def _compose_base_metadata(self, text: str) -> dict:
        scan = self._dictionary_scan(text)
        return {
            "scoring_mode": self._resolve_scoring_mode(),
            "scoring_method": "dictionary",
            "dict_score": scan["dict_score"],
            "dictionary_severity_signal": scan["dictionary_severity_signal"],
            "matched_terms": scan["matched_terms"],
            "matched_phrases": scan["matched_phrases"],
            "matched_term_spans": scan["matched_term_spans"],
            "matched_phrase_spans": scan["matched_phrase_spans"],
            "hf_score": None,
            "hf_adjusted_score": None,
            "weighted_dict_score": scan["dict_score"],
            "final_score": scan["dict_score"],
        }

    def analyze_message(self, message: Message) -> tuple[float, dict]:
        metadata = self._compose_base_metadata(message.content)
        mode = metadata["scoring_mode"]
        dict_score = float(metadata["dict_score"])
        final_score = dict_score

        if self._hf_available():
            if mode == SCORING_MODE_HYBRID_MODEL_PRIORITY:
                hf_score = self.hf_model.predict_single(message.content)
                adjusted_hf_score, adjustment = self._apply_hf_context_guard(message.content, dict_score, hf_score)

                weighted_dict_score = dict_score * float(self.config.hybrid_dictionary_weight)
                final_score = max(adjusted_hf_score, weighted_dict_score)

                metadata["hf_score"] = hf_score
                metadata["hf_adjusted_score"] = adjusted_hf_score
                metadata["weighted_dict_score"] = weighted_dict_score
                metadata["scoring_method"] = "hybrid_model_priority"
                if adjustment:
                    metadata["context_adjustment"] = adjustment
            else:
                # legacy behavior
                if dict_score < self.config.hf_fallback_threshold:
                    hf_score = self.hf_model.predict_single(message.content)
                    adjusted_hf_score, adjustment = self._apply_hf_context_guard(message.content, dict_score, hf_score)
                    metadata["hf_score"] = hf_score
                    metadata["hf_adjusted_score"] = adjusted_hf_score
                    if adjustment:
                        metadata["context_adjustment"] = adjustment

                    if adjusted_hf_score > dict_score:
                        final_score = adjusted_hf_score
                        metadata["scoring_method"] = "huggingface_context_guard" if adjustment else "huggingface"
                else:
                    metadata["scoring_method"] = "dictionary_fast_track"
        else:
            metadata["scoring_method"] = "dictionary"

        metadata["final_score"] = final_score
        message.update_toxicity(final_score, threshold=self.config.toxicity_threshold)
        setattr(message, "scoring_metadata", metadata)
        return final_score, metadata

    def analyze_messages_batch(self, messages: list[Message]) -> list[tuple[float, dict]]:
        mode = self._resolve_scoring_mode()
        scores_metadata: list[dict] = []
        hf_candidates: list[tuple[int, Message]] = []

        for i, message in enumerate(messages):
            metadata = self._compose_base_metadata(message.content)
            dict_score = float(metadata["dict_score"])
            scores_metadata.append({"final_score": dict_score, "metadata": metadata})

            if self._hf_available():
                if mode == SCORING_MODE_HYBRID_MODEL_PRIORITY:
                    hf_candidates.append((i, message))
                elif dict_score < self.config.hf_fallback_threshold:
                    hf_candidates.append((i, message))
                else:
                    metadata["scoring_method"] = "dictionary_fast_track"

        if hf_candidates:
            texts = [msg.content for _, msg in hf_candidates]
            hf_scores = self.hf_model.predict_batch(texts)

            for (idx, msg), hf_score in zip(hf_candidates, hf_scores):
                item = scores_metadata[idx]
                metadata = item["metadata"]
                dict_score = float(metadata["dict_score"])
                adjusted_hf_score, adjustment = self._apply_hf_context_guard(msg.content, dict_score, hf_score)

                metadata["hf_score"] = hf_score
                metadata["hf_adjusted_score"] = adjusted_hf_score
                if adjustment:
                    metadata["context_adjustment"] = adjustment

                if mode == SCORING_MODE_HYBRID_MODEL_PRIORITY:
                    weighted_dict_score = dict_score * float(self.config.hybrid_dictionary_weight)
                    item["final_score"] = max(adjusted_hf_score, weighted_dict_score)
                    metadata["weighted_dict_score"] = weighted_dict_score
                    metadata["scoring_method"] = "hybrid_model_priority"
                else:
                    if adjusted_hf_score > dict_score:
                        item["final_score"] = adjusted_hf_score
                        metadata["scoring_method"] = "huggingface_context_guard" if adjustment else "huggingface"

        results = []
        for msg, data in zip(messages, scores_metadata):
            final_score = float(data["final_score"])
            metadata = data["metadata"]
            metadata["final_score"] = final_score
            msg.update_toxicity(final_score, threshold=self.config.toxicity_threshold)
            setattr(msg, "scoring_metadata", metadata)
            results.append((final_score, metadata))

        return results

