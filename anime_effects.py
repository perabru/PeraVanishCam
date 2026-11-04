"""Live shadow clones and an original female anime transformation avatar."""
from __future__ import annotations

from pathlib import Path
import sys
import cv2
import numpy as np

try:
    from .naruto_effect import _smoke_layer
except ImportError:
    from naruto_effect import _smoke_layer

AVATAR_PATH = Path(__file__).resolve().parent / 'assets' / 'transformation_avatar.png'
BURST_SECONDS = 1.45


def load_avatar(path: Path | None = None) -> np.ndarray:
    if path is None:
        folder = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        external = folder / "personagem.png"
        path = external if external.is_file() else AVATAR_PATH
    sprite = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if sprite is None or sprite.ndim != 3 or sprite.shape[2] != 4:
        raise RuntimeError('Personagem nao encontrada ou sem transparencia. Use uma imagem PNG RGBA.')
    if sprite[:, :, 3].max() < 20 or sprite[:, :, 3].min() >= 250:
        raise RuntimeError('A personagem precisa ter fundo transparente e pixels visiveis.')
    # Crop only at render time so the supplied PNG is preserved unchanged.
    visible = cv2.findNonZero((sprite[:, :, 3] > 16).astype(np.uint8))
    x, y, w, h = cv2.boundingRect(visible)
    return sprite[y:y+h, x:x+w].copy()


def person_bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    count, _, stats, _ = cv2.connectedComponentsWithStats((mask > .45).astype(np.uint8))
    if count <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[i]
    if area < max(25, mask.size * .002):
        return None
    return int(x), int(y), int(w), int(h)


def _paste(output: np.ndarray, rgb: np.ndarray, alpha: np.ndarray, x: int, y: int, opacity=1.0) -> None:
    h, w = rgb.shape[:2]
    left, top = max(0, x), max(0, y)
    right, bottom = min(output.shape[1], x+w), min(output.shape[0], y+h)
    if left >= right or top >= bottom:
        return
    crop = np.s_[top-y:bottom-y, left-x:right-x]
    a = np.clip(alpha[crop] * opacity, 0, 1)[:, :, None]
    target = output[top:bottom, left:right]
    target[:] = np.clip(rgb[crop].astype(np.float32) * a + target * (1-a), 0, 255).astype(np.uint8)


def _smoke(output: np.ndarray, x: float, y: float, size: float, age: float) -> None:
    if age >= BURST_SECONDS:
        return
    anchor = (int(x), int(y), max(24, int(size)))
    _smoke_layer(output, anchor, max(.02, age), False)
    _smoke_layer(output, anchor, max(.02, age), True)


def render_clones(frame: np.ndarray, background: np.ndarray, mask: np.ndarray, age: float) -> np.ndarray:
    bounds = person_bounds(mask)
    if bounds is None:
        return frame.copy()
    x, y, w, h = bounds
    pad = 3
    x0, y0 = max(0, x-pad), max(0, y-pad)
    x1, y1 = min(frame.shape[1], x+w+pad), min(frame.shape[0], y+h+pad)
    person, alpha = frame[y0:y1, x0:x1], np.clip(mask[y0:y1, x0:x1], 0, 1)
    canvas = background.copy()
    scale = min(.80, frame.shape[1] * .33 / max(1, person.shape[1]))
    target_w, target_h = max(1, round(person.shape[1]*scale)), max(1, round(person.shape[0]*scale))
    clone = cv2.resize(person, (target_w, target_h), interpolation=cv2.INTER_AREA)
    clone_alpha = cv2.resize(alpha, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    opacity = min(1.0, max(0.0, (age-.05)/.28))
    bottom = min(frame.shape[0], y1)
    anchors = []
    for ratio in (.19, .81):
        cx = int(frame.shape[1]*ratio)
        left = int(np.clip(cx-target_w//2, 0, max(0, frame.shape[1]-target_w)))
        top = max(0, bottom-target_h)
        _paste(canvas, clone, clone_alpha, left, top, opacity)
        anchors.append((left+target_w/2, top+target_h/2, target_h*.65))
    _paste(canvas, frame, np.clip(mask, 0, 1), 0, 0)
    for cx, cy, size in anchors:
        _smoke(canvas, cx, cy, size, age)
    return canvas


def render_transformation(frame: np.ndarray, background: np.ndarray, mask: np.ndarray,
                          sprite: np.ndarray, age: float,
                          cache: dict[int, np.ndarray] | None = None) -> np.ndarray:
    bounds = person_bounds(mask)
    if bounds is None:
        return background.copy()
    x, y, w, h = bounds
    output = background.copy()
    target_h = max(24, min(frame.shape[0], int(h*1.05)))
    # Quantize sizes and bound the cache so motion cannot grow it indefinitely.
    target_h = max(24, (target_h//8)*8)
    target_w = max(1, round(target_h*sprite.shape[1]/sprite.shape[0]))
    sized = cache.get(target_h) if cache is not None else None
    if sized is None:
        sized = cv2.resize(sprite, (target_w, target_h), interpolation=cv2.INTER_AREA)
        if cache is not None:
            if len(cache) >= 16:
                cache.clear()
            cache[target_h] = sized
    left = int(np.clip(x+w/2-target_w/2, 0, max(0, frame.shape[1]-target_w)))
    top = int(np.clip(y+h-target_h, 0, max(0, frame.shape[0]-target_h)))
    reveal = min(1.0, max(0.0, (age-.06)/.24))
    _paste(output, sized[:, :, :3], sized[:, :, 3].astype(np.float32)/255, left, top, reveal)
    if age < .30:
        original_alpha = np.clip(mask, 0, 1) * (1-reveal)
        _paste(output, frame, original_alpha, 0, 0)
    _smoke(output, left+target_w/2, top+target_h/2, target_h*.68, age)
    return output
