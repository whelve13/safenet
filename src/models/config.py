from dataclasses import dataclass, field

@dataclass
class AnalysisConfig:
    toxicity_threshold: float = 0.7

    # Escalation detector: how many recent messages to consider
    escalation_window_size: int = 5

    # Escalation detector: minimum score increase between halves to trigger escalation
    escalation_sensitivity: float = 0.3

    # Graph: minimum number of distinct aggressors to qualify as gang-up
    min_gang_up_aggressors: int = 2

    # Risk engine: users scoring above this are pushed to the priority queue
    high_risk_floor: float = 0.3

    # Additional toxic words added by the user (word -> weight)
    custom_toxic_words: dict[str, float] = field(default_factory=dict)

    # Additional toxic phrases added by the user (phrase -> weight)
    custom_toxic_phrases: dict[str, float] = field(default_factory=dict)