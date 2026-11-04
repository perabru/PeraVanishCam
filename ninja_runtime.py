"""Interactive camera loop for the clone and transformation jutsus."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import ExitStack
import time

import cv2
import numpy as np

try:
    from .anime_effects import load_avatar, render_clones, render_transformation
    from .jutsu_gestures import SealGate
    from .vanish_sound import VanishSound
except ImportError:
    from anime_effects import load_avatar, render_clones, render_transformation
    from jutsu_gestures import SealGate
    from vanish_sound import VanishSound

HELP_WINDOW = 'PeraVanishCam - Guia de gestos'


@dataclass
class NinjaState:
    selected: str = 'clones'
    active: str | None = None
    activated_at: float = 0.0

    def activate(self, sign: str, now: float) -> None:
        if sign not in ('clones', 'transform'):
            raise ValueError('Jutsu desconhecido')
        self.selected = self.active = sign
        self.activated_at = now

    def reset(self) -> None:
        self.active = None


def gesture_help() -> np.ndarray:
    panel = np.full((470, 820, 3), (28, 23, 35), np.uint8)
    ink, cyan, purple = (244, 239, 249), (218, 216, 70), (227, 147, 183)
    cv2.putText(panel, 'SELOS NINJA', (35, 45), cv2.FONT_HERSHEY_SIMPLEX, .85, ink, 2, cv2.LINE_AA)
    for x, title in [(35, 'CLONES: CRUZ (+)'), (430, 'TRANSFORMAR: TIGRE')]:
        cv2.putText(panel, title, (x, 90), cv2.FONT_HERSHEY_SIMPLEX, .60, ink, 1, cv2.LINE_AA)
    # Paired thick strokes represent each hand's index and middle fingers.
    for offset in (-9, 9):
        cv2.line(panel, (205+offset, 250), (205+offset, 125), cyan, 13, cv2.LINE_AA)
        cv2.line(panel, (125, 175+offset), (285, 175+offset), purple, 13, cv2.LINE_AA)
        cv2.line(panel, (590+offset, 250), (590+offset, 125), cyan, 13, cv2.LINE_AA)
        cv2.line(panel, (630+offset, 250), (630+offset, 125), purple, 13, cv2.LINE_AA)
    lines = [
        ('Duas maos; indicador e medio esticados.', 320),
        ('Outros dedos dobrados. Segure o selo por 0,65 s.', 351),
        ('Abaixe as maos antes de fazer outro selo.', 382),
        ('C: clones  |  T: transformar  |  R: voltar  |  H: fechar guia', 432),
    ]
    for text, y in lines:
        cv2.putText(panel, text, (35, y), cv2.FONT_HERSHEY_SIMPLEX, .57, ink, 1, cv2.LINE_AA)
    return panel


def self_test_effects() -> None:
    sprite = load_avatar()
    background = np.full((160, 240, 3), 30, np.uint8)
    frame = background.copy()
    frame[25:150, 93:147] = (60, 110, 190)
    mask = np.zeros((160, 240), np.float32)
    mask[25:150, 93:147] = 1
    for output in (render_clones(frame, background, mask, 2),
                   render_transformation(frame, background, mask, sprite, 2)):
        if output.shape != frame.shape or output.dtype != np.uint8 or np.array_equal(output, background):
            raise RuntimeError('Falha no teste dos novos efeitos ninja.')
    print('[PeraVanishCam] Clones, transformacao e personagem verificados.')


def run_ninja_camera(args, resources: ExitStack, mode: str, api) -> int:
    api.download_models('naruto')
    capture = api.open_camera(args.camera, args.width, args.height)
    resources.callback(capture.release)
    capture.set(cv2.CAP_PROP_FPS, args.fps)
    segmenter, tracker = api.create_tasks('naruto')
    resources.callback(segmenter.close)
    resources.callback(tracker.close)
    sound = VanishSound(getattr(args, 'sound', None))
    resources.callback(sound.close)
    avatar = load_avatar(getattr(args, 'avatar', None))
    resources.callback(cv2.destroyAllWindows)
    cv2.namedWindow(api.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(api.WINDOW_NAME, args.width, args.height)
    fullscreen = bool(args.fullscreen)
    if fullscreen:
        api.set_fullscreen(True)
    state, gate = NinjaState(selected=mode), SealGate()
    avatar_cache: dict[int, np.ndarray] = {}
    background, mask = None, None
    samples = []
    now = time.perf_counter()
    started = calibration_started = now
    last_mask = last_gesture = float('-inf')
    last_report = float('-inf')
    last_countdown = None
    virtual, virtual_initialized = None, False
    help_open = False
    print('[PeraVanishCam] Saia do enquadramento por 4 segundos para capturar o fundo.')
    print('[PeraVanishCam] Selos: dedos em CRUZ = clones; dedos juntos/TIGRE = transformar.')
    print('[PeraVanishCam] Segure o selo por 0,65 s. Depois abaixe as maos antes de repetir.')
    print('[PeraVanishCam] C clones | T transformar | V efeito selecionado | R voltar | H guia | ESPACO fundo | Q sair')
    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError('A webcam parou de enviar imagens.')
            if not args.no_mirror:
                frame = cv2.flip(frame, 1)
            height, width = frame.shape[:2]
            now = time.perf_counter()
            if not virtual_initialized:
                virtual = api.open_virtual_camera(args, width, height)
                virtual_initialized = True
                if virtual is not None:
                    resources.callback(virtual.close)
            if background is not None and background.shape != frame.shape:
                background, mask = None, None
                calibration_started, last_countdown = now, None
                samples.clear()
                state.reset()
                gate.disarm(now)
            image = None
            timestamp_ms = int((now-started)*1000)
            if background is None:
                elapsed = now-calibration_started
                remaining = max(0, int(np.ceil(api.CALIBRATION_SECONDS-elapsed)))
                if remaining != last_countdown:
                    print(f'[PeraVanishCam] Capturando o fundo: {remaining} segundos.')
                    last_countdown = remaining
                if elapsed >= api.CALIBRATION_SECONDS-api.BACKGROUND_SAMPLE_SECONDS:
                    samples.append(frame.copy())
                    samples[:] = samples[-12:]
                if elapsed >= api.CALIBRATION_SECONDS:
                    background = np.median(np.stack(samples), axis=0).astype(np.uint8) if samples else frame.copy()
                    samples.clear()
                    print('[PeraVanishCam] Fundo pronto. Volte para a camera; H mostra os selos.')
                display = frame
            else:
                if now-last_gesture >= .10:
                    last_gesture = now
                    image = api.mp.Image(image_format=api.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    sign = tracker.recognize_seal(image, timestamp_ms)
                    fired = gate.update(sign, now)
                    if args.gesture_debug and now-last_report >= 1:
                        print(f'[PeraVanishCam] Maos={tracker.last_hand_count}, selo={sign or "nenhum"}, efeito={state.active or "normal"}')
                        last_report = now
                    if fired:
                        state.activate(fired, now)
                        sound.play()
                        print(f'[PeraVanishCam] Jutsu ativado: {fired}. R para voltar.')
                if state.active:
                    if mask is None or now-last_mask >= .065:
                        if image is None:
                            image = api.mp.Image(image_format=api.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        mask = api.person_mask(segmenter, image, timestamp_ms, width, height)
                        last_mask = now
                    age = now-state.activated_at
                    if state.active == 'clones':
                        display = render_clones(frame, background, mask, age)
                    else:
                        display = render_transformation(frame, background, mask, avatar, age, avatar_cache)
                else:
                    display = frame
            if virtual is not None:
                api.send_virtual_frame(virtual, display)
            cv2.imshow(api.WINDOW_NAME, display)
            if help_open:
                cv2.imshow(HELP_WINDOW, gesture_help())
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27) or cv2.getWindowProperty(api.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord(' '):
                background, mask = None, None
                samples.clear()
                calibration_started, last_countdown = now, None
                state.reset()
                gate.disarm(now)
                print('[PeraVanishCam] Saia do quadro por 4 segundos para capturar o novo fundo.')
            elif key == ord('r'):
                state.reset()
                gate.disarm(now)
            elif key in (ord('c'), ord('t'), ord('v')) and background is not None:
                selected = 'clones' if key == ord('c') else 'transform' if key == ord('t') else state.selected
                state.activate(selected, now)
                gate.disarm(now)
                sound.play()
            elif key == ord('f'):
                fullscreen = not fullscreen
                api.set_fullscreen(fullscreen)
            elif key == ord('h'):
                help_open = not help_open
                if help_open:
                    cv2.namedWindow(HELP_WINDOW, cv2.WINDOW_AUTOSIZE)
                else:
                    cv2.destroyWindow(HELP_WINDOW)
            if virtual is not None:
                virtual.sleep_until_next_frame()
    finally:
        resources.close()
    return 0
