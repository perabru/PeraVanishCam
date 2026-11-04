"""Live shadow clones with clean cutout scaling and a smoke entrance."""
from __future__ import annotations

import cv2
import numpy as np

try:
    from .naruto_effect import EFFECT_SECONDS, _smoke_layer
except ImportError:
    from naruto_effect import EFFECT_SECONDS, _smoke_layer

BURST_SECONDS = EFFECT_SECONDS


def _clean_alpha(mask: np.ndarray) -> np.ndarray:
    return np.clip(np.nan_to_num(mask, nan=0.0, posinf=1.0, neginf=0.0), 0, 1).astype(np.float32)


def person_bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Keep the main person and nearby detached hands, excluding tiny noise."""
    alpha = _clean_alpha(mask)
    count, _, stats, _ = cv2.connectedComponentsWithStats((alpha > .20).astype(np.uint8))
    if count <= 1:
        return None
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[largest]
    if area < max(25, mask.size * .002):
        return None
    # Segmentation may briefly disconnect a raised hand from the torso. Include
    # nearby substantial components instead of cutting the hand from each clone.
    left, top, right, bottom = int(x), int(y), int(x+w), int(y+h)
    reach_x, reach_y = max(12, int(w*.6)), max(12, int(h*.30))
    for component in stats[1:]:
        px, py, pw, ph, pixels = map(int, component)
        if pixels < max(6, int(mask.size*.00008)):
            continue
        if px+pw >= x-reach_x and px <= x+w+reach_x and py+ph >= y-reach_y and py <= y+h+reach_y:
            left, top = min(left, px), min(top, py)
            right, bottom = max(right, px+pw), max(bottom, py+ph)
    return left, top, right-left, bottom-top


def _resize_cutout(rgb: np.ndarray, alpha: np.ndarray,
                   size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Resize premultiplied color and coverage together to avoid color fringes."""
    alpha = _clean_alpha(alpha)
    premultiplied = rgb.astype(np.float32)*alpha[:, :, None]
    method = cv2.INTER_AREA if size[0] <= rgb.shape[1] and size[1] <= rgb.shape[0] else cv2.INTER_LINEAR
    color = cv2.resize(premultiplied, size, interpolation=method)
    coverage = cv2.resize(alpha, size, interpolation=method)
    return color, np.clip(coverage, 0, 1)


def _paste_premultiplied(output: np.ndarray, color: np.ndarray, alpha: np.ndarray,
                         x: int, y: int, opacity: float = 1.0) -> None:
    h, w = color.shape[:2]
    left, top = max(0, x), max(0, y)
    right, bottom = min(output.shape[1], x+w), min(output.shape[0], y+h)
    if left >= right or top >= bottom or opacity <= 0:
        return
    crop = np.s_[top-y:bottom-y, left-x:right-x]
    strength = float(np.clip(opacity, 0, 1))
    a = alpha[crop][:, :, None]
    target = output[top:bottom, left:right]
    blended = color[crop]*strength + target.astype(np.float32)*(1-a*strength)
    target[:] = np.rint(np.clip(blended, 0, 255)).astype(np.uint8)


def _paste(output: np.ndarray, rgb: np.ndarray, alpha: np.ndarray,
           x: int, y: int, opacity: float = 1.0) -> None:
    coverage = _clean_alpha(alpha)
    _paste_premultiplied(output, rgb.astype(np.float32)*coverage[:, :, None], coverage, x, y, opacity)


def _smoke(output: np.ndarray, anchor: tuple[int, int, int], age: float,
           foreground: bool) -> None:
    if 0 <= age < BURST_SECONDS:
        _smoke_layer(output, anchor, max(.02, age), foreground)


def render_clones(frame: np.ndarray, background: np.ndarray, mask: np.ndarray,
                   age: float) -> np.ndarray:
    bounds = person_bounds(mask)
    if bounds is None:
        return frame.copy()
    x, y, w, h = bounds
    pad = max(3, round(min(frame.shape[:2])*.006))
    x0, y0 = max(0, x-pad), max(0, y-pad)
    x1, y1 = min(frame.shape[1], x+w+pad), min(frame.shape[0], y+h+pad)
    person, alpha = frame[y0:y1, x0:x1], _clean_alpha(mask[y0:y1, x0:x1])
    canvas = background.copy()
    # Never upscale a camera face. More of the native detail is retained at
    # 86% size, with a width cap leaving room for the original in the center.
    scale = min(.86, frame.shape[1]*.33/max(1, person.shape[1]))
    target_w = max(1, round(person.shape[1]*scale))
    target_h = max(1, round(person.shape[0]*scale))
    clone, clone_alpha = _resize_cutout(person, alpha, (target_w, target_h))
    opacity = float(np.clip((age-.08)/.30, 0, 1))
    placements = []
    for ratio in (.18, .82):
        cx = int(frame.shape[1]*ratio)
        left = int(np.clip(cx-target_w//2, 0, max(0, frame.shape[1]-target_w)))
        top = max(0, y1-target_h)
        anchor = (left+target_w//2, top+round(target_h*.50), max(24, round(target_h*.72)))
        placements.append((left, top, anchor))
        _smoke(canvas, anchor, age, foreground=False)
        _paste_premultiplied(canvas, clone, clone_alpha, left, top, opacity)
    # The original retains its exact native colors and texture; only the alpha
    # matte is improved. No face smoothing, sharpening, or generated pixels.
    _paste(canvas, person, alpha, x0, y0)
    for _, _, anchor in placements:
        _smoke(canvas, anchor, age, foreground=True)
    return canvas
