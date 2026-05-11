import unittest

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.config import AnalysisConfig
from src.algorithms.hf_toxicity_model import HFToxicityModel


class TestHFToxicityModelScoring(unittest.TestCase):
    def setUp(self):
        # Disable model loading for pure scoring tests.
        self.model = HFToxicityModel(AnalysisConfig(use_hf_model=False))

    def test_non_toxic_label_does_not_map_to_high_toxicity(self):
        score = self.model._normalize_score({"label": "non-toxic", "score": 0.99})
        self.assertLess(score, 0.05)

    def test_toxic_label_maps_to_high_toxicity(self):
        score = self.model._normalize_score({"label": "toxic", "score": 0.91})
        self.assertGreater(score, 0.9)

    def test_binary_scores_use_toxic_probability(self):
        score = self.model._normalize_score([
            {"label": "non-toxic", "score": 0.98},
            {"label": "toxic", "score": 0.02},
        ])
        self.assertAlmostEqual(score, 0.02, places=4)


if __name__ == "__main__":
    unittest.main()
