import unittest
from unittest.mock import patch

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.config import AnalysisConfig
from src.services.moderation_service import ModerationService
from src.algorithms.hf_toxicity_model import HFToxicityModel


class TestModerationService(unittest.TestCase):
    def test_dictionary_only_result_mapping(self):
        config = AnalysisConfig(use_hf_model=False)
        service = ModerationService(config)

        result = service.analyze_text("kys")
        self.assertEqual(result["severity"], "critical")
        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["detection_method"], "dictionary")
        self.assertEqual(result["explanation"]["contributors"], ["dictionary"])

    def test_hybrid_detection_when_both_contribute(self):
        config = AnalysisConfig(use_hf_model=True, scoring_mode="hybrid_model_priority")
        with patch.object(HFToxicityModel, "_load_pipeline", return_value=None):
            with patch.object(HFToxicityModel, "predict_single", return_value=0.9):
                service = ModerationService(config)
                service.analyzer.hf_model.is_loaded = True

                result = service.analyze_text("you are an idiot")
                self.assertEqual(result["detection_method"], "hybrid")
                self.assertIn("toxic-bert", result["explanation"]["contributors"])
                self.assertIn("idiot", result["explanation"]["matched_terms"])
                self.assertTrue(any(span["term"] == "idiot" for span in result["explanation"]["matched_term_spans"]))
                self.assertAlmostEqual(result["explanation"]["hf_score"], 0.9)
                self.assertEqual(result["decision"], "block")

    def test_toxic_bert_only_detection(self):
        config = AnalysisConfig(use_hf_model=True, scoring_mode="hybrid_model_priority")
        with patch.object(HFToxicityModel, "_load_pipeline", return_value=None):
            with patch.object(HFToxicityModel, "predict_single", return_value=0.72):
                service = ModerationService(config)
                service.analyzer.hf_model.is_loaded = True

                result = service.analyze_text("this sentence is implicitly hostile")
                self.assertEqual(result["detection_method"], "toxic-bert")
                self.assertEqual(result["severity"], "high")
                self.assertEqual(result["decision"], "blur")

    def test_event_hash_normalizes_snippet_and_domain(self):
        service = ModerationService(AnalysisConfig(use_hf_model=False))
        result = {
            "snippet": " You  are   toxic  ",
            "toxicity_score": 0.8,
            "severity": "high",
            "decision": "blur",
            "detection_method": "dictionary",
            "explanation": {"reason": "test"},
        }
        event_1 = service.build_event(result, source="extension", page_url="https://EXAMPLE.com/path")
        event_2 = service.build_event(
            {**result, "snippet": "you are toxic"},
            source="extension",
            page_url="https://example.com/another",
        )
        self.assertEqual(event_1.event_hash, event_2.event_hash)

    def test_persist_only_for_blur_or_block(self):
        self.assertFalse(ModerationService.should_persist_event("allow"))
        self.assertTrue(ModerationService.should_persist_event("blur"))
        self.assertTrue(ModerationService.should_persist_event("block"))


if __name__ == "__main__":
    unittest.main()

