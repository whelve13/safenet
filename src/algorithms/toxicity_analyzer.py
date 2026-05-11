import re
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.models.message import Message
from src.models.config import AnalysisConfig
from src.structures.trie import Trie
from src.algorithms.string_matching import kmp_search
from src.algorithms.hf_toxicity_model import HFToxicityModel

# default vocabulary built into the system
DEFAULT_TOXIC_WORDS: dict[str, float] = {
    "idiot": 0.5, "stupid": 0.4, "loser": 0.6,
    "ugly": 0.5, "die": 1.0, "kill": 1.0, "hate": 0.7,
    "dumb": 0.4, "trash": 0.6, "freak": 0.5,
    "moron": 0.5, "pathetic": 0.6, "retard": 0.9,
    "worthless": 0.8, "disgusting": 0.6, "useless": 0.5,
    "scum": 0.7, "creep": 0.5, "weirdo": 0.4,
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
}

POSITIVE_PROFANITY_IDIOM_PATTERN = re.compile(
    r"\b(?:fucking|fuckin)\s+(?:awesome|amazing|great|fantastic|brilliant|epic|cool)\b"
)


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

    def analyze_message(self, message: Message) -> tuple[float, dict]:
        # calculates the toxicity score of a given message
        score = 0.0
        content = message.content.lower()
        metadata = {"scoring_method": "dictionary", "dict_score": 0.0, "hf_score": None}

        # word-level analysis using Trie
        words = re.findall(r'\b\w+\b', content)
        for word in words:
            found, weight = self.abusive_trie.search(word)
            if found:
                score += weight

        # phrase-level analysis using KMP String Matching
        for phrase, weight in self.abusive_phrases.items():
            matches = kmp_search(content, phrase)
            if matches:
                score += weight * len(matches)

        dict_score = min(score, 1.0)
        metadata["dict_score"] = dict_score
        final_score = dict_score

        # hybrid logic: run HF model if dict score is low
        if self.config.use_hf_model and self.hf_model.is_loaded:
            if dict_score < self.config.hf_fallback_threshold:
                hf_score = self.hf_model.predict_single(message.content)
                metadata["hf_score"] = hf_score
                adjusted_hf_score, adjustment = self._apply_hf_context_guard(message.content, dict_score, hf_score)
                if adjustment:
                    metadata["hf_adjusted_score"] = adjusted_hf_score
                    metadata["context_adjustment"] = adjustment
                 
                # Take the max or override based on hybrid strategy
                if adjusted_hf_score > dict_score:
                    final_score = adjusted_hf_score
                    metadata["scoring_method"] = "huggingface_context_guard" if adjustment else "huggingface"
            else:
                metadata["scoring_method"] = "dictionary_fast_track"

        # update the message object using the configurable threshold
        message.update_toxicity(final_score, threshold=self.config.toxicity_threshold)
        # Store metadata directly on the message object dynamically, or just return it
        setattr(message, "scoring_metadata", metadata)
        
        return final_score, metadata

    def analyze_messages_batch(self, messages: list[Message]) -> list[tuple[float, dict]]:
        # Fast dictionary scoring first
        scores_metadata = []
        hf_candidates = []  # List of tuples: (index, message)
        
        for i, message in enumerate(messages):
            score = 0.0
            content = message.content.lower()
            metadata = {"scoring_method": "dictionary", "dict_score": 0.0, "hf_score": None}

            # word-level
            words = re.findall(r'\b\w+\b', content)
            for word in words:
                found, weight = self.abusive_trie.search(word)
                if found:
                    score += weight

            # phrase-level
            for phrase, weight in self.abusive_phrases.items():
                matches = kmp_search(content, phrase)
                if matches:
                    score += weight * len(matches)

            dict_score = min(score, 1.0)
            metadata["dict_score"] = dict_score
            scores_metadata.append({"final_score": dict_score, "metadata": metadata})

            if self.config.use_hf_model and self.hf_model.is_loaded:
                if dict_score < self.config.hf_fallback_threshold:
                    hf_candidates.append((i, message))
                else:
                    metadata["scoring_method"] = "dictionary_fast_track"

        # Batch HF inference
        if hf_candidates:
            texts = [msg.content for _, msg in hf_candidates]
            hf_scores = self.hf_model.predict_batch(texts)
            
            for (idx, _), hf_score in zip(hf_candidates, hf_scores):
                item = scores_metadata[idx]
                item["metadata"]["hf_score"] = hf_score
                adjusted_hf_score, adjustment = self._apply_hf_context_guard(
                    messages[idx].content,
                    item["metadata"]["dict_score"],
                    hf_score,
                )
                if adjustment:
                    item["metadata"]["hf_adjusted_score"] = adjusted_hf_score
                    item["metadata"]["context_adjustment"] = adjustment
                 
                if adjusted_hf_score > item["metadata"]["dict_score"]:
                    item["final_score"] = adjusted_hf_score
                    item["metadata"]["scoring_method"] = "huggingface_context_guard" if adjustment else "huggingface"

        # Finalize
        results = []
        for msg, data in zip(messages, scores_metadata):
            final_score = data["final_score"]
            metadata = data["metadata"]
            msg.update_toxicity(final_score, threshold=self.config.toxicity_threshold)
            setattr(msg, "scoring_metadata", metadata)
            results.append((final_score, metadata))

        return results
