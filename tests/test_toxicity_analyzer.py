import unittest
from datetime import datetime
from unittest.mock import patch

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.config import AnalysisConfig
from src.models.message import Message
from src.algorithms.toxicity_analyzer import ToxicityAnalyzer
from src.algorithms.hf_toxicity_model import HFToxicityModel

class TestToxicityAnalyzer(unittest.TestCase):

    def setUp(self):
        # Create a base config
        self.config = AnalysisConfig()
        
    def _create_message(self, content: str) -> Message:
        return Message(
            id="msg-1",
            timestamp=datetime.now(),
            sender_id="user_a",
            content=content
        )

    def test_dictionary_only_mode(self):
        """Test that the dictionary mode works and bypasses HF when HF is disabled."""
        self.config.use_hf_model = False
        analyzer = ToxicityAnalyzer(self.config)
        
        msg = self._create_message("You are an idiot and stupid")
        score, metadata = analyzer.analyze_message(msg)
        
        # 'idiot' is 0.5, 'stupid' is 0.4 in default vocab. Total = 0.9
        self.assertAlmostEqual(score, 0.9)
        self.assertEqual(metadata["scoring_method"], "dictionary")
        self.assertEqual(metadata["dict_score"], 0.9)
        self.assertIsNone(metadata["hf_score"])

    def test_hf_fast_track(self):
        """Test that obvious dictionary hits bypass HF model even if enabled, if dict_score >= threshold."""
        self.config.use_hf_model = True
        self.config.hf_fallback_threshold = 0.8
        
        # Mock HF model to ensure it's NOT called
        with patch.object(HFToxicityModel, '_load_pipeline', return_value=None):
            with patch.object(HFToxicityModel, 'predict_single', return_value=0.99) as mock_predict:
                analyzer = ToxicityAnalyzer(self.config)
                # Force it to be loaded so the logic triggers
                analyzer.hf_model.is_loaded = True 
                
                # 'kys' has a weight of 1.0 in default phrase dict, which is >= 0.8 threshold
                msg = self._create_message("just kys")
                score, metadata = analyzer.analyze_message(msg)
                
                # Predict should not have been called because dict_score (1.0) >= 0.8
                mock_predict.assert_not_called()
                self.assertEqual(score, 1.0)
                self.assertEqual(metadata["scoring_method"], "dictionary_fast_track")

    def test_hf_fallback_implicit_toxicity(self):
        """Test that implicit toxicity triggers the HF model if dict score is low."""
        self.config.use_hf_model = True
        self.config.hf_fallback_threshold = 0.8
        
        with patch.object(HFToxicityModel, '_load_pipeline', return_value=None):
            with patch.object(HFToxicityModel, 'predict_single', return_value=0.85) as mock_predict:
                analyzer = ToxicityAnalyzer(self.config)
                analyzer.hf_model.is_loaded = True
                
                # "you are a complete waste of space" might not be in the dictionary, so dict_score = 0.0
                msg = self._create_message("you are a complete waste of space")
                score, metadata = analyzer.analyze_message(msg)
                
                mock_predict.assert_called_once_with("you are a complete waste of space")
                self.assertEqual(score, 0.85)
                self.assertEqual(metadata["scoring_method"], "huggingface")
                self.assertEqual(metadata["dict_score"], 0.0)
                self.assertEqual(metadata["hf_score"], 0.85)

    def test_hf_failure_fallback(self):
        """Test that the system gracefully falls back to dict score if HF fails to load or crashes."""
        self.config.use_hf_model = True
        
        # simulate model not being loaded (e.g., missing dependencies)
        with patch.object(HFToxicityModel, '_load_pipeline', return_value=None):
            analyzer = ToxicityAnalyzer(self.config)
            analyzer.hf_model.is_loaded = False
        
            msg = self._create_message("mildly offensive text")
            score, metadata = analyzer.analyze_message(msg)
            
            # It should just return the dict_score (0.0 in this case)
            self.assertEqual(score, 0.0)
            self.assertEqual(metadata["scoring_method"], "dictionary")

    def test_batch_processing(self):
        """Test that batch processing correctly routes to HF and dict based on thresholds."""
        self.config.use_hf_model = True
        self.config.hf_fallback_threshold = 0.8
        
        with patch.object(HFToxicityModel, '_load_pipeline', return_value=None):
            with patch.object(HFToxicityModel, 'predict_batch', return_value=[0.85]) as mock_predict:
                analyzer = ToxicityAnalyzer(self.config)
                analyzer.hf_model.is_loaded = True
                
                msg1 = self._create_message("kys") # 1.0 dict score -> fast track
                msg2 = self._create_message("sneaky abusive text") # 0.0 dict score -> hf model
                
                results = analyzer.analyze_messages_batch([msg1, msg2])
                
                self.assertEqual(len(results), 2)
                
                # Check msg1
                self.assertEqual(results[0][0], 1.0)
                self.assertEqual(results[0][1]["scoring_method"], "dictionary_fast_track")
                
                # Check msg2
                self.assertEqual(results[1][0], 0.85)
                self.assertEqual(results[1][1]["scoring_method"], "huggingface")
                
                # Batch predict should have only been called with msg2's content
                mock_predict.assert_called_once_with(["sneaky abusive text"])

    def test_hf_context_guard_for_positive_idiom_single(self):
        self.config.use_hf_model = True
        self.config.hf_fallback_threshold = 0.8
        self.config.hf_positive_idiom_cap = 0.35

        with patch.object(HFToxicityModel, '_load_pipeline', return_value=None):
            with patch.object(HFToxicityModel, 'predict_single', return_value=0.9865):
                analyzer = ToxicityAnalyzer(self.config)
                analyzer.hf_model.is_loaded = True

                msg = self._create_message("that was fucking awesome")
                score, metadata = analyzer.analyze_message(msg)

                self.assertAlmostEqual(score, 0.35)
                self.assertFalse(msg.is_flagged)
                self.assertEqual(metadata["scoring_method"], "huggingface_context_guard")
                self.assertEqual(metadata["context_adjustment"], "positive_profanity_idiom")

    def test_hf_context_guard_for_positive_idiom_batch(self):
        self.config.use_hf_model = True
        self.config.hf_fallback_threshold = 0.8
        self.config.hf_positive_idiom_cap = 0.35

        with patch.object(HFToxicityModel, '_load_pipeline', return_value=None):
            with patch.object(HFToxicityModel, 'predict_batch', return_value=[0.99, 0.92]):
                analyzer = ToxicityAnalyzer(self.config)
                analyzer.hf_model.is_loaded = True

                msg1 = self._create_message("that was fucking awesome")
                msg2 = self._create_message("you are a complete waste of space")
                results = analyzer.analyze_messages_batch([msg1, msg2])

                self.assertAlmostEqual(results[0][0], 0.35)
                self.assertEqual(results[0][1]["scoring_method"], "huggingface_context_guard")
                self.assertEqual(results[1][0], 0.92)
                self.assertEqual(results[1][1]["scoring_method"], "huggingface")

if __name__ == '__main__':
    unittest.main()
