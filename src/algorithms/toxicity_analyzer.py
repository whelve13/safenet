import re
import sys
import os

# Add src to path to allow absolute imports if run directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.models.message import Message
from src.models.config import AnalysisConfig
from src.structures.trie import Trie
from src.algorithms.string_matching import kmp_search

# Default vocabulary built into the system
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


class ToxicityAnalyzer:
    """
    Analyzes message content to determine toxicity using custom Data Structures and Algorithms.
    Utilizes a Trie for fast exact word lookup and KMP for complex phrase matching.
    """
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config or AnalysisConfig()
        self.abusive_trie = Trie()
        self.abusive_phrases: dict[str, float] = {}

        self._load_vocabulary()

    def _load_vocabulary(self):
        """Loads the built-in + user-defined toxic vocabulary."""
        # Built-in words
        for word, weight in DEFAULT_TOXIC_WORDS.items():
            self.abusive_trie.insert(word, weight)

        # User-defined custom words from config
        for word, weight in self.config.custom_toxic_words.items():
            self.abusive_trie.insert(word.lower(), weight)

        # Built-in phrases
        self.abusive_phrases = dict(DEFAULT_TOXIC_PHRASES)

        # User-defined custom phrases from config
        for phrase, weight in self.config.custom_toxic_phrases.items():
            self.abusive_phrases[phrase.lower()] = weight

    def analyze_message(self, message: Message) -> float:
        """
        Calculates the toxicity score of a given message.
        Time Complexity: O(W * L + P * (N+M))
        where W is number of words, L is max word length, P is number of phrases.
        """
        score = 0.0
        content = message.content.lower()

        # 1. Word-level analysis using Trie
        words = re.findall(r'\b\w+\b', content)
        for word in words:
            found, weight = self.abusive_trie.search(word)
            if found:
                score += weight

        # 2. Phrase-level analysis using KMP String Matching
        for phrase, weight in self.abusive_phrases.items():
            matches = kmp_search(content, phrase)
            if matches:
                score += weight * len(matches)

        # Cap the score at 1.0 for a single message
        final_score = min(score, 1.0)

        # Update the message object using the configurable threshold
        message.update_toxicity(final_score, threshold=self.config.toxicity_threshold)
        return final_score
