import os
import tempfile
import unittest
from unittest.mock import patch

import app


def voice(name, locale):
    return {"ShortName": name, "Locale": locale}


class TtsVoiceTests(unittest.TestCase):
    def test_supported_languages_resolve_to_their_language(self):
        catalog = [
            voice(app.EDGE_TTS_VOICES[code], app.EDGE_TTS_LOCALES[code])
            for code in app.LANGUAGES.values()
        ]
        for code in app.LANGUAGES.values():
            with self.subTest(language=code):
                selected = app.resolve_tts_voice(code, catalog)
                self.assertTrue(selected.lower().startswith(app.EDGE_TTS_LOCALES[code].lower()))

    def test_missing_language_voice_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "no voice"):
            app.resolve_tts_voice("mr", [voice("en-US-AriaNeural", "en-US")])

    def test_empty_voice_catalog_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "no available voices"):
            app.resolve_tts_voice("hi", [])


class TtsAsyncTests(unittest.TestCase):
    def test_one_failed_segment_does_not_stop_later_segments(self):
        requests = [
            {"index": 0, "text": "bad", "path": "bad.mp3"},
            {"index": 1, "text": "good", "path": "good.mp3"},
        ]

        async def fake_synthesize(text, voice, path):
            if text == "bad":
                raise RuntimeError("provider rejected segment")

        with patch.object(app, "_edge_tts_synthesize", fake_synthesize):
            app._run_async(app._synthesize_segments(
                requests, "hi-IN-SwaraNeural", 1, 0, None, None
            ))

        self.assertIn("error", requests[0])
        self.assertNotIn("error", requests[1])

    def test_retry_is_bounded(self):
        attempts = []

        async def fake_synthesize(text, voice, path):
            attempts.append(1)
            raise TimeoutError("timed out")

        with patch.object(app, "_edge_tts_synthesize", fake_synthesize):
            with self.assertRaises(RuntimeError):
                app._run_async(app._synthesize_with_retry(
                    "नमस्ते", "hi-IN-SwaraNeural", "unused.mp3", 1, 1
                ))
        self.assertEqual(len(attempts), 2)


class AudioValidationTests(unittest.TestCase):
    def test_playback_selection_never_uses_missing_dubbed_track(self):
        self.assertEqual(
            app.select_playback_audio("original.wav", "dubbed.wav", True),
            "dubbed.wav",
        )
        self.assertEqual(
            app.select_playback_audio("original.wav", None, True),
            "original.wav",
        )
        self.assertEqual(
            app.select_playback_audio("original.wav", "dubbed.wav", False),
            "original.wav",
        )

    def test_owned_temp_file_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "owned.mp3")
            with open(path, "wb") as output:
                output.write(b"temporary")
            self.assertTrue(app.remove_file_silent(path))
            self.assertFalse(os.path.exists(path))

    def test_empty_and_corrupt_audio_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = os.path.join(directory, "empty.wav")
            open(empty, "wb").close()
            with self.assertRaisesRegex(RuntimeError, "empty"):
                app.probe_audio_file(empty)

            corrupt = os.path.join(directory, "corrupt.wav")
            with open(corrupt, "wb") as output:
                output.write(b"not audio")
            with self.assertRaises(RuntimeError):
                app.probe_audio_file(corrupt)


if __name__ == "__main__":
    unittest.main()
