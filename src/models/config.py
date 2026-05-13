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

    # --- Machine Learning Extensions ---
    # Scoring strategy:
    # - "hybrid_model_priority": default, always evaluate HF when available and blend with dictionary signal.
    # - "dictionary_first_fallback": legacy behavior, use HF only when dictionary score is below fallback threshold.
    scoring_mode: str = "hybrid_model_priority"
    hybrid_dictionary_weight: float = 0.85
    use_hf_model: bool = True
    hf_model_name: str = "unitary/toxic-bert"
    hf_fallback_threshold: float = 0.8  # Use HF if dict score < this threshold
    hf_inference_mode: str = "local"  # 'local' or 'api'
    hf_batch_size: int = 16
    hf_max_length: int = 128
    hf_device: int = -1  # -1 for CPU, 0+ for GPU
    hf_context_guard_enabled: bool = True
    hf_context_guard_min_hf_score: float = 0.8
    hf_positive_idiom_cap: float = 0.35
