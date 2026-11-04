"""Verify custom sound selection and decode the bundled MP3."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_app import vanish_sound as audio


class SoundTests(unittest.TestCase):
    def test_portable_sound_override_and_builtin_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            with patch.object(audio.sys, "frozen", True, create=True), patch.object(audio.sys, "executable", str(folder / "VanishCam.exe")):
                self.assertEqual(audio.resolve_sound_path(), audio.SOUND_PATH)
                (folder / "som.wav").write_bytes(b"wav")
                self.assertEqual(audio.resolve_sound_path(), folder / "som.wav")
                (folder / "som.mp3").write_bytes(b"mp3")
                self.assertEqual(audio.resolve_sound_path(), folder / "som.mp3")
                chosen = folder / "outro.wav"
                self.assertEqual(audio.resolve_sound_path(chosen), chosen)

    def test_missing_explicit_sound_does_not_silently_use_default(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "nao encontrado"):
                audio.VanishSound(Path(directory) / "missing.wav")

    def test_bundled_mp3_decodes_and_plays_with_headless_audio_driver(self):
        with patch.dict(os.environ, SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1"):
            sound = audio.VanishSound(audio.SOUND_PATH)
            try:
                self.assertIsNone(sound.ffplay)
                self.assertGreater(sound.sound.get_length(), 0)
                sound.play()
                self.assertTrue(sound.mixer.get_busy())
            finally:
                sound.close()


if __name__ == "__main__":
    unittest.main()
