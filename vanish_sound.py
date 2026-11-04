"""Preload the Naruto MP3 and play it without blocking video frames."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


SOUND_PATH = Path(__file__).resolve().parent / "assets" / "vanish.MP3"


def resolve_sound_path(path: Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    folder = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for name in ("som.mp3", "som.wav"):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return SOUND_PATH


class VanishSound:
    def __init__(self, path: Path | None = None):
        path = resolve_sound_path(path)
        if not path.is_file():
            raise RuntimeError(f"Audio Naruto nao encontrado: {path}")
        self.path = path

        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        self.process = None
        self.ffplay = None
        try:
            from pygame import mixer
        except ImportError:
            self.ffplay = shutil.which("ffplay")
            if self.ffplay is None:
                raise RuntimeError("Para reproduzir o som, instale pygame ou ffplay.")
            return

        self.mixer = mixer
        self.owns_mixer = mixer.get_init() is None
        try:
            if self.owns_mixer:
                mixer.init(frequency=44100, size=-16, channels=2, buffer=256)
            self.sound = mixer.Sound(str(path))  # Decode once, before opening the webcam.
        except Exception as error:
            if self.owns_mixer:
                mixer.quit()
            raise RuntimeError(f"Nao foi possivel abrir o audio Naruto: {error}") from error

    def play(self) -> None:
        if self.ffplay is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            try:
                self.process = subprocess.Popen(
                    [self.ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet",
                     "-i", str(self.path)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                raise RuntimeError(f"Nao foi possivel reproduzir o audio Naruto: {error}") from error
            return
        self.sound.stop()
        if self.sound.play() is None:
            raise RuntimeError("Nao foi possivel reproduzir o audio Naruto: nenhum canal de audio livre.")

    def wait(self) -> None:
        if self.ffplay is not None:
            if self.process is not None:
                self.process.wait()
            return
        while self.mixer.get_busy():
            time.sleep(0.02)

    def close(self) -> None:
        if self.ffplay is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            return
        if self.owns_mixer:
            self.mixer.quit()
            self.owns_mixer = False
