"""Two-hand trigger and smoke/log compositing for body substitution."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


try:
    from .realistic_smoke import render_smoke_layer
except ImportError:
    from realistic_smoke import render_smoke_layer


EFFECT_SECONDS = 1.80
LOG_PATH = Path(__file__).resolve().parent / "assets" / "substitution_log.png"
LOG_CACHE_MAX_BYTES = 32 * 1024 * 1024
LOG_CACHE_MAX_ENTRIES = 8


def joined_hands_from_landmarks(hands, width: int, height: int) -> bool:
    """Recognize two nearby, similarly oriented open hands in image space."""
    if len(hands) < 2:
        return False
    points = [np.array([(p.x * width, p.y * height) for p in hand])
              for hand in hands[:2] if len(hand) == 21]
    if len(points) != 2 or not all(np.isfinite(hand).all() for hand in points):
        return False
    palms = [hand[[0, 5, 9, 13, 17]].mean(axis=0) for hand in points]
    scale = [max(float(np.linalg.norm(hand[5] - hand[17])),
                 float(np.linalg.norm(hand[0] - hand[9]))) for hand in points]
    if min(scale) < 8.0 or max(scale) > min(scale) * 2.2:
        return False
    size = sum(scale) * 0.5
    directions = [hand[9] - hand[0] for hand in points]
    alignment = float(np.dot(*directions) /
                      max(1e-6, np.linalg.norm(directions[0]) * np.linalg.norm(directions[1])))
    fingertips = [hand[[8, 12, 16, 20]].mean(axis=0) for hand in points]
    return (
        alignment > 0.25
        and np.linalg.norm(palms[0] - palms[1]) < size * 1.55
        and np.linalg.norm(fingertips[0] - fingertips[1]) < size * 1.9
    )


def substitution_anchor(mask: np.ndarray) -> tuple[int, int, int]:
    """Place the log at the person's torso instead of at a fixed screen spot."""
    height, width = mask.shape
    binary = (mask > 0.45).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
    if count <= 1:
        return width // 2, height // 2, int(height * 0.57)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, _ = stats[largest]
    size = int(np.clip(h * 0.58, height * 0.24, height * 0.70))
    center_x = int(np.clip(x + w * 0.5, size // 3, width - size // 3))
    center_y = int(np.clip(y + h * 0.52, size // 3, height - size // 3))
    return center_x, center_y, size


def load_log() -> np.ndarray:
    sprite = cv2.imread(str(LOG_PATH), cv2.IMREAD_UNCHANGED)
    if sprite is None or sprite.ndim != 3 or sprite.shape[2] != 4:
        raise RuntimeError(f"Imagem do tronco indisponivel: {LOG_PATH}")
    # Some PNG encoders produce 253/254 instead of full coverage. Normalize
    # opacity without changing the photographed bark or its actual silhouette.
    alpha = sprite[:, :, 3]
    peak = int(alpha.max())
    if peak == 0:
        raise RuntimeError('A imagem do tronco esta vazia.')
    sprite[:, :, 3] = np.rint(alpha.astype(np.float32)*(255.0/peak)).astype(np.uint8)
    return sprite


def overlay_log(frame: np.ndarray, sprite: np.ndarray, anchor: tuple[int, int, int],
                opacity: float = 1.0, scale: float = 1.0,
                cache: dict[int, np.ndarray] | None = None) -> None:
    if opacity <= 0:
        return
    cx, cy, target_height = anchor
    # Resize premultiplied colors so transparent border RGB cannot leak into
    # the log's outline. Cubic interpolation preserves detail when enlarging.
    height = max(1, int(target_height * scale))
    width = max(1, int(height * sprite.shape[1] / sprite.shape[0]))
    sized = cache.get(height) if cache is not None else None
    if sized is None:
        premultiplied = sprite.astype(np.float32) / 255.0
        premultiplied[:, :, :3] *= premultiplied[:, :, 3:4]
        interpolation = cv2.INTER_AREA if height < sprite.shape[0] else cv2.INTER_CUBIC
        sized = np.clip(cv2.resize(premultiplied, (width, height), interpolation=interpolation), 0, 1)
        # Cubic ringing must never create a color brighter than its coverage.
        sized[:, :, :3] = np.minimum(sized[:, :, :3], sized[:, :, 3:4])
        if cache is not None and sized.nbytes <= LOG_CACHE_MAX_BYTES:
            # Native-resolution float RGBA sprites can each occupy several
            # MiB. Bound bytes as well as entries when the person changes size.
            cached_bytes = sum(image.nbytes for image in cache.values())
            while cache and (len(cache) >= LOG_CACHE_MAX_ENTRIES or
                             cached_bytes + sized.nbytes > LOG_CACHE_MAX_BYTES):
                oldest = cache.pop(next(iter(cache)))
                cached_bytes -= oldest.nbytes
            cache[height] = sized
    x1, y1 = cx - width // 2, cy - height // 2
    x2, y2 = x1 + width, y1 + height
    left, top = max(0, x1), max(0, y1)
    right, bottom = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if left >= right or top >= bottom:
        return
    # A soft contact shadow tightens as the wood reaches the lower frame edge.
    # It is evaluated in a small ROI, so HD output does not need a shadow buffer.
    distance = max(0, frame.shape[0] - (cy + height*.48))
    contact = math.exp(-distance/max(1, height*.45))
    shadow_rx = max(2, width*(.35 + .18*(1-contact)))
    shadow_ry = max(1.5, height*(.022 + .024*(1-contact)))
    sy = frame.shape[0]-max(2, height*.018)
    sx0, sx1 = max(0, int(cx-shadow_rx*2.5)), min(frame.shape[1], int(cx+shadow_rx*2.5)+1)
    sy0, sy1 = max(0, int(sy-shadow_ry*3)), frame.shape[0]
    if sx0 < sx1 and sy0 < sy1:
        yy, xx = np.mgrid[sy0:sy1, sx0:sx1]
        shadow = np.exp(-.5*(((xx-cx)/shadow_rx)**2 + ((yy-sy)/shadow_ry)**2))
        shadow *= .30*contact*float(np.clip(opacity, 0, 1))
        destination = frame[sy0:sy1, sx0:sx1]
        destination[:] = np.rint(destination*(1-shadow[:, :, None])).astype(np.uint8)
    part = sized[top - y1:bottom - y1, left - x1:right - x1]
    opacity = float(np.clip(opacity, 0, 1))
    alpha = part[:, :, 3:4] * opacity
    # Match ambient exposure with a bounded gain; never recolor the live person.
    sample = frame[::max(1, frame.shape[0]//24), ::max(1, frame.shape[1]//32)]
    exposure = float(np.clip(.62 + np.mean(sample)/510., .62, 1.08))
    destination = frame[top:bottom, left:right]
    destination[:] = np.clip(
        part[:, :, :3] * (255.0 * opacity * exposure)
        + destination.astype(np.float32) * (1.0 - alpha),
        0, 255,
    ).astype(np.uint8)


def landed_log_anchor(anchor: tuple[int, int, int], frame_height: int) -> tuple[int, int, int]:
    cx, cy, size = anchor
    return cx, max(cy, frame_height - round(size * 0.48)), size


def falling_log_anchor(anchor: tuple[int, int, int], frame_height: int,
                       age: float) -> tuple[int, int, int]:
    """Accelerate downwards, touch the frame floor, then settle with a small bounce."""
    cx, cy, size = anchor
    floor_y = landed_log_anchor(anchor, frame_height)[1]
    distance = floor_y - cy
    if distance <= 0 or age <= 0.18:
        return anchor
    elapsed = age - 0.18
    gravity = frame_height * 3.2
    fall = gravity * elapsed * elapsed * 0.5
    if fall < distance:
        return cx, cy + round(fall), size
    landed_at = math.sqrt(2.0 * distance / gravity)
    bounce_age = elapsed - landed_at
    bounce = size * 0.075 * math.exp(-5.0 * bounce_age) * abs(math.sin(11.0 * bounce_age))
    return cx, floor_y - round(bounce), size


def _smoke_layer(frame: np.ndarray, anchor: tuple[int, int, int],
                 age: float, foreground: bool) -> None:
    render_smoke_layer(frame, anchor, age, foreground, EFFECT_SECONDS)



def render_substitution(frame: np.ndarray, background: np.ndarray, mask: np.ndarray,
                        sprite: np.ndarray, anchor: tuple[int, int, int], age: float,
                        log_cache: dict[int, np.ndarray] | None = None) -> np.ndarray:
    """Quick body replacement, expanding smoke, then a persistent wooden log."""
    if age >= EFFECT_SECONDS:
        output = background.copy()
        overlay_log(output, sprite, landed_log_anchor(anchor, output.shape[0]), cache=log_cache)
        return output
    if age >= 0.13:
        output = background.copy()
    else:
        person_alpha = mask * max(0.0, 1.0 - age / 0.13)
        output = (
            frame.astype(np.float32) * person_alpha[:, :, None]
            + background.astype(np.float32) * (1.0 - person_alpha[:, :, None])
        ).astype(np.uint8)
    _smoke_layer(output, anchor, age, foreground=False)
    log_opacity = min(1.0, max(0.0, (age - 0.05) / 0.15))
    moving_anchor = falling_log_anchor(anchor, output.shape[0], age)
    overlay_log(output, sprite, moving_anchor, log_opacity,
                scale=1.15 - min(age, 0.25) * 0.6, cache=log_cache)
    _smoke_layer(output, anchor, age, foreground=True)
    return output
