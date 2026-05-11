import logging
from typing import List

# Attempt to load ML dependencies gracefully
try:
    from transformers import pipeline, Pipeline
    import torch
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    Pipeline = None

from src.models.config import AnalysisConfig

APPROVED_HF_MODEL = "unitary/toxic-bert"

TOXIC_LABELS = {
    "toxic",
    "label_1",
    "abusive",
    "hate",
    "hateful",
    "offensive",
    "insult",
    "1",
}

NON_TOXIC_LABELS = {
    "non-toxic",
    "non_toxic",
    "label_0",
    "clean",
    "neutral",
    "safe",
    "0",
}


class HFToxicityModel:
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.model_name = APPROVED_HF_MODEL
        self.model: Pipeline | None = None
        self.is_loaded = False
        self.load_error = None

        if not self.config.use_hf_model:
            return

        if not ML_AVAILABLE:
            self.load_error = "transformers or torch not installed. Please install requirements-ml.txt."
            logging.warning(self.load_error)
            return

        self._load_pipeline()

    def _load_pipeline(self):
        try:
            if self.config.hf_model_name != self.model_name:
                logging.info(
                    "Ignoring configured HF model '%s'. Using approved model '%s'.",
                    self.config.hf_model_name,
                    self.model_name,
                )
            logging.info(f"Loading Hugging Face model: {self.model_name}")
            
            # M\map -1 to -1 (CPU), 0+ to GPU depending on device presence
            device = self.config.hf_device
            if device < 0 and torch.cuda.is_available():
                pass
                
            self.model = pipeline(
                "text-classification",
                model=self.model_name,
                device=device,
                truncation=True,
                max_length=self.config.hf_max_length
            )
            self.is_loaded = True
            logging.info("Hugging Face model loaded successfully.")
        except Exception as e:
            self.load_error = str(e)
            logging.error(f"Failed to load Hugging Face model: {e}")
            self.model = None
            self.is_loaded = False

    @staticmethod
    def _normalize_label(label: str) -> str:
        return str(label).strip().lower().replace(" ", "_")

    @staticmethod
    def _clamp_score(score: float) -> float:
        return min(max(score, 0.0), 1.0)

    def _score_from_single_prediction(self, prediction: dict) -> float:
        label = self._normalize_label(prediction.get("label", ""))
        score = float(prediction.get("score", 0.0))

        if label in NON_TOXIC_LABELS or ("non" in label and "toxic" in label):
            return self._clamp_score(1.0 - score)
        if label in TOXIC_LABELS:
            return self._clamp_score(score)

        # conservative fallback for unknown labels
        return 0.0

    def _normalize_score(self, prediction) -> float:
        if isinstance(prediction, dict):
            return self._score_from_single_prediction(prediction)

        if isinstance(prediction, list):
            if not prediction:
                return 0.0

            if isinstance(prediction[0], list):
                return self._normalize_score(prediction[0])

            toxic_prob = None
            non_toxic_prob = None

            for item in prediction:
                if not isinstance(item, dict):
                    continue
                label = self._normalize_label(item.get("label", ""))
                score = float(item.get("score", 0.0))

                if label in NON_TOXIC_LABELS or ("non" in label and "toxic" in label):
                    non_toxic_prob = score if non_toxic_prob is None else max(non_toxic_prob, score)
                elif label in TOXIC_LABELS:
                    toxic_prob = score if toxic_prob is None else max(toxic_prob, score)

            if toxic_prob is not None and non_toxic_prob is not None:
                denom = toxic_prob + non_toxic_prob
                if denom > 0:
                    return self._clamp_score(toxic_prob / denom)
            if toxic_prob is not None:
                return self._clamp_score(toxic_prob)
            if non_toxic_prob is not None:
                return self._clamp_score(1.0 - non_toxic_prob)
            return 0.0

        return 0.0

    def predict_single(self, text: str) -> float:
        if not self.is_loaded or not self.model:
            return 0.0
            
        try:
            # handle empty strings which might crash some pipelines
            if not text.strip():
                return 0.0
                
            result = self.model(
                text,
                truncation=True,
                max_length=self.config.hf_max_length,
                top_k=None,
            )
            return self._normalize_score(result)
        except Exception as e:
            logging.error(f"HF inference error on single text: {e}")
            return 0.0

    def predict_batch(self, texts: List[str]) -> List[float]:
        if not self.is_loaded or not self.model:
            return [0.0] * len(texts)
            
        try:
            # replace empty strings with a safe space to avoid crashes
            safe_texts = [t if t.strip() else " " for t in texts]
            
            results = self.model(
                safe_texts, 
                batch_size=self.config.hf_batch_size,
                truncation=True,
                max_length=self.config.hf_max_length,
                top_k=None,
            )
            
            return [self._normalize_score(res) for res in results]
        except Exception as e:
            logging.error(f"HF inference error on batch: {e}")
            return [0.0] * len(texts)