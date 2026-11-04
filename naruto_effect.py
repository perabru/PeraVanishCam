"""Two-hand trigger and smoke/log compositing for body substitution."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


EFFECT_SECONDS = 1.45
LOG_PATH = Path(__file__).resolve().parent / "assets" / "substitution_log.png"


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
        if cache is not None:
            if len(cache) >= 24:
                cache.clear()
            cache[height] = sized
    x1, y1 = cx - width // 2, cy - height // 2
    x2, y2 = x1 + width, y1 + height
    left, top = max(0, x1), max(0, y1)
    right, bottom = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if left >= right or top >= bottom:
        return
    part = sized[top - y1:bottom - y1, left - x1:right - x1]
    opacity = float(np.clip(opacity, 0, 1))
    alpha = part[:, :, 3:4] * opacity
    destination = frame[top:bottom, left:right]
    destination[:] = np.clip(
        part[:, :, :3] * (255.0 * opacity)
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


@lru_cache(maxsize=1)
def _smoke_resources() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Small reusable flow texture and stable particles, independent of video size."""
    rng = np.random.default_rng(9127)
    noise = np.zeros((256, 256), np.float32)
    for side, weight in ((8, .55), (24, .30), (64, .15)):
        field = rng.random((side, side), dtype=np.float32) - .5
        noise += cv2.resize(field, (256, 256), interpolation=cv2.INTER_CUBIC) * weight
    particles = []
    for seed, count in ((1934, 34), (9127, 30)):
        generator = np.random.default_rng(seed)
        # angle, radial distance, radius, aspect, rotation, density, swirl phase
        values = np.column_stack((generator.uniform(0, math.tau, count),
                                  generator.uniform(.05, 1, count),
                                  generator.uniform(.12, .24, count),
                                  generator.uniform(.68, 1.05, count),
                                  generator.uniform(-45, 45, count),
                                  generator.uniform(160, 245, count),
                                  generator.uniform(0, math.tau, count)))
        particles.append(values)
    return noise, particles[0], particles[1]


def _smoke_layer(frame: np.ndarray, anchor: tuple[int, int, int],
                 age: float, foreground: bool) -> None:
    """Expanding, lit billows and curling wisps, rendered in a bounded local field."""
    if not 0 < age < EFFECT_SECONDS:
        return
    cx, cy, size = anchor
    if size <= 0 or not np.isfinite(age):
        return
    reveal = min(1.0, age / .13)
    reveal = reveal * reveal * (3 - 2 * reveal)
    fade = max(0.0, 1.0 - max(0.0, age - .43) / (EFFECT_SECONDS - .43))
    fade = fade * fade * (3 - 2 * fade)
    # Calculate bounds before allocating; even a very large 4K subject never
    # causes a huge smoke simulation or a full-frame float RGBA allocation.
    margin = max(8, math.ceil(size * 1.52))
    left, top = max(0, cx - margin), max(0, cy - margin)
    right, bottom = min(frame.shape[1], cx + margin + 1), min(frame.shape[0], cy + margin + 1)
    if left >= right or top >= bottom:
        return
    output_w, output_h = right-left, bottom-top
    sample_scale = min(1.0, 416.0 / (margin*2+1))
    width, height = max(1, round(output_w*sample_scale)), max(1, round(output_h*sample_scale))
    density = np.zeros((height, width), np.uint8)
    noise, back, front = _smoke_resources()
    growth = min(age, 1.05)
    radius = size * (.23 + .57 * growth)
    drift = age * size * .20
    for angle, distance, puff_size, aspect, rotation, opacity, phase in (front if foreground else back):
        swirl = .16 * math.sin(phase + age*2.1)
        px = cx + math.cos(angle+swirl) * radius * distance
        py = cy + math.sin(angle+swirl) * radius * distance * .78 - drift
        puff = size * puff_size * (.82 + .72*growth)
        axes = (max(1, round(puff*sample_scale)), max(1, round(puff*aspect*sample_scale)))
        center = (round((px-left)*sample_scale), round((py-top)*sample_scale))
        cv2.ellipse(density, center, axes, float(rotation+age*12), 0, 360,
                    int(opacity), -1, cv2.LINE_AA)
    # A soft core makes the replacement read as a burst, rather than a ring.
    core = (round((cx-left)*sample_scale), round((cy-drift*.6-top)*sample_scale))
    cv2.ellipse(density, core,
                (max(1, round(size*.29*sample_scale)), max(1, round(size*.36*sample_scale))),
                0, 0, 360, 218 if foreground else 180, -1, cv2.LINE_AA)
    blur = max(.65, min(4.8, size * sample_scale * .013))
    density = cv2.GaussianBlur(density, (0, 0), blur).astype(np.float32) / 255.0
    flow = cv2.warpAffine(noise, np.float32([
        [1, 0, (cx-left)*sample_scale-128+age*15],
        [0, 1, (cy-top)*sample_scale-128-age*21],
    ]), (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    # Gentle texture modulates opacity without rough, pixel-sized edges.
    density *= np.clip(1 + flow*.58, .70, 1.20)
    dx = cv2.Sobel(density, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(density, cv2.CV_32F, 0, 1, ksize=3)
    lighting = np.clip(-(dx+dy)*1.8, -.9, .9)
    shade = np.clip((186 if foreground else 150) + density*49 + lighting*29 + flow*23, 105, 248)
    alpha = np.clip(density * (1.05 if foreground else .75) * reveal * fade, 0, .94)
    # Thin curls remain in the cloud, with blurred highlights instead of hard
    # white strokes. Drawn at the same capped resolution to keep costs stable.
    wisps = np.zeros((height, width), np.uint8)
    for direction in (-1, 1):
        points = []
        for t in np.linspace(0, math.pi*1.45, 32):
            spiral = (.11 + .11*t) * size * (.7 + .35*growth)
            px = cx + direction * (math.cos(t+age*.65)*spiral + size*.12)
            py = cy + math.sin(t+age*.65)*spiral*.48 - drift
            points.append((round((px-left)*sample_scale), round((py-top)*sample_scale)))
        cv2.polylines(wisps, [np.asarray(points, np.int32)], False, 255,
                      max(1, round(size*.012*sample_scale)), cv2.LINE_AA)
    wisps = cv2.GaussianBlur(wisps, (0, 0), max(.6, blur*.55)).astype(np.float32)/255
    shade = np.minimum(250, shade + wisps*29)
    # Crop transparent margins before HD upsampling and blend in OpenCV's
    # SIMD path. Uniform smoke color remains valid outside its alpha support,
    # so interpolating this lit scalar field does not create dark RGB fringes.
    occupied = cv2.findNonZero((alpha > .001).astype(np.uint8))
    if occupied is None:
        return
    x, y, w, h = cv2.boundingRect(occupied)
    target_left, target_top = math.floor(x*output_w/width), math.floor(y*output_h/height)
    target_right = min(output_w, math.ceil((x+w)*output_w/width))
    target_bottom = min(output_h, math.ceil((y+h)*output_h/height))
    target_size = (target_right-target_left, target_bottom-target_top)
    opacity = cv2.resize(alpha[y:y+h, x:x+w], target_size, interpolation=cv2.INTER_LINEAR)
    light = cv2.resize(shade[y:y+h, x:x+w], target_size, interpolation=cv2.INTER_LINEAR)
    cloud = cv2.merge(((light-5).astype(np.uint8), (light-1).astype(np.uint8), light.astype(np.uint8)))
    target = frame[top+target_top:top+target_bottom, left+target_left:left+target_right]
    cv2.blendLinear(cloud, target, opacity, 1-opacity, dst=target)



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
