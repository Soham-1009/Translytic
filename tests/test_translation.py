import unittest
from unittest.mock import patch, MagicMock

from app import translate_segments


class TranslationTests(unittest.TestCase):
    def test_cancellation(self):
        with self.assertRaises(InterruptedError):
            translate_segments(
                [{"start": 0, "end": 1, "text": "hello"}],
                "hi", "Hindi",
                check_cancel=lambda: True
            )

    def test_empty_segments(self):
        self.assertEqual(translate_segments([], "hi", "Hindi"), [])

    @patch("app.OPENROUTER_API_KEY", "")
    @patch("app.GoogleTranslator")
    def test_fallback_to_google_translate(self, mock_gt_cls):
        mock_gt = MagicMock()
        mock_gt.translate.return_value = "नमस्ते"
        mock_gt_cls.return_value = mock_gt

        segments = [{"start": 0, "end": 1, "text": "hello"}]
        results = translate_segments(segments, "hi", "Hindi")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "नमस्ते")
        self.assertFalse(results[0]["translation_failed"])

    @patch("app.OPENROUTER_API_KEY", "")
    @patch("app.GoogleTranslator")
    def test_failed_translation_retains_source(self, mock_gt_cls):
        mock_gt = MagicMock()
        mock_gt.translate.side_effect = Exception("network down")
        mock_gt_cls.return_value = mock_gt

        segments = [{"start": 0, "end": 1, "text": "hello"}]
        results = translate_segments(segments, "hi", "Hindi")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["text"], "hello")
        self.assertTrue(results[0]["translation_failed"])
        self.assertIn("network down", results[0]["translation_error"])

    @patch("app.OPENROUTER_API_KEY", "")
    @patch("app.time.sleep")
    @patch("app.GoogleTranslator")
    def test_google_rate_limit_is_retried_and_duplicate_text_is_cached(
        self, mock_gt_cls, mock_sleep
    ):
        mock_gt = MagicMock()
        mock_gt.translate.side_effect = [
            Exception("TooManyRequests: 429"),
            "नमस्ते",
        ]
        mock_gt_cls.return_value = mock_gt

        segments = [
            {"start": 0, "end": 1, "text": "hello"},
            {"start": 1, "end": 2, "text": "hello"},
        ]
        results = translate_segments(segments, "hi", "Hindi")

        self.assertEqual([segment["text"] for segment in results], ["नमस्ते", "नमस्ते"])
        self.assertFalse(any(segment["translation_failed"] for segment in results))
        self.assertEqual(mock_gt.translate.call_count, 2)

    @patch("app.OPENROUTER_API_KEY", "")
    @patch("app.time.sleep")
    @patch("app.GoogleTranslator")
    @patch("app.MyMemoryTranslator")
    def test_mymemory_fallback_translates_after_google_rate_limit(
        self, mock_mm_cls, mock_gt_cls, mock_sleep
    ):
        mock_gt_cls.return_value.translate.side_effect = Exception("429 TooManyRequests")
        mock_mm_cls.return_value.translate.return_value = "नमस्ते"

        results = translate_segments(
            [{"start": 0, "end": 1, "text": "Hello", "source_language": "en"}],
            "hi", "Hindi",
        )

        self.assertEqual(results[0]["text"], "नमस्ते")
        self.assertFalse(results[0]["translation_failed"])
        mock_mm_cls.assert_called_once_with(source="english", target="hindi")


if __name__ == "__main__":
    unittest.main()
