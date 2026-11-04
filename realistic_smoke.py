"""Texture-driven smoke with optical-depth layers and continuous turbulent flow.

All simulation buffers are bounded; compositing alone runs at camera resolution.
The source PNG is premultiplied before any resampling to keep transparent edges
free from black/white fringes.
"""
from __future__ import annotations

from functools import lru_cache
import math
from pathlib import Path

import cv2
import numpy as np

SMOKE_PATH = Path(__file__).resolve().parent / 'assets' / 'smoke_cloud.png'


def _smooth(value: float) -> float:
    value = float(np.clip(value, 0, 1))
    return value * value * (3 - 2 * value)


@lru_cache(maxsize=1)
def smoke_resources() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sprite = cv2.imread(str(SMOKE_PATH), cv2.IMREAD_UNCHANGED)
    if sprite is None or sprite.ndim != 3 or sprite.shape[2] != 4:
        raise RuntimeError(f'Textura de fumaca indisponivel: {SMOKE_PATH}')
    rgba = sprite.astype(np.float32) / 255
    if not np.any(rgba[:, :, 3] > 0) or not np.any(rgba[:, :, 3] == 0):
        raise RuntimeError('A textura de fumaca precisa ter transparencia real.')
    rgba[:, :, :3] *= rgba[:, :, 3:4]
    rgba = cv2.resize(rgba, (384, 384), interpolation=cv2.INTER_AREA)
    rng = np.random.default_rng(1934)
    noise = np.zeros((192, 192, 2), np.float32)
    for side, weight in ((5, .52), (13, .30), (31, .18)):
        grid = rng.uniform(-1, 1, (side, side, 2)).astype(np.float32)
        noise += cv2.resize(grid, (192, 192), interpolation=cv2.INTER_CUBIC) * weight
    # Reproducible puff trajectories, fixed between video frames.
    puffs = np.array([
        [-.23, .11, .82, -17, .84],
        [.25, .08, .79, 26, .78],
        [-.03, -.25, .93, -4, .93],
        [.03, .30, .72, 55, .65],
    ], np.float32)
    return rgba, noise, puffs


@lru_cache(maxsize=12)
def _smoke_field(resolution: int, age: float, foreground: bool,
                 duration: float) -> tuple[np.ndarray, int, int] | None:
    """Normalized field reused by both clones; cache stays below 10 MiB."""
    size = (resolution-1)/3.2
    center = (resolution-1)/2
    sprite, noise, puffs = smoke_resources()
    depth = np.zeros((resolution, resolution), np.float32)
    light_sum = np.zeros_like(depth)
    growth = 1 - math.exp(-age * 4.5)
    base_radius = size * (.26 + .56*growth)
    drift = size * age * .23
    for i, (dx, dy, scale, rotation, strength) in enumerate(puffs):
        phase = i*1.73 + (1.1 if foreground else 0)
        spread = size * (.32 + age*.26)
        x = center + dx*spread + math.sin(age*1.5+phase)*size*.055
        y = center + dy*spread - drift*(.65+i*.12)
        radius = base_radius * scale
        turn = float(rotation + age*(7 if i%2 else -9) + (114 if foreground else 0))
        transform = cv2.getRotationMatrix2D((191.5, 191.5), turn, 2*radius/384)
        transform[:, 2] += (x-191.5, y-191.5)
        puff = cv2.warpAffine(sprite, transform, (resolution, resolution),
                              flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        coverage = puff[:, :, 3]
        luminance = cv2.cvtColor(puff[:, :, :3], cv2.COLOR_BGR2GRAY)
        unassociated = np.divide(luminance, np.maximum(coverage, .001))
        local_depth = coverage * strength * (.65 + unassociated*.55)
        depth += local_depth
        light_sum += unassociated * local_depth
    # Continuous flow moves the fine internal texture independently of expansion.
    flow = cv2.warpAffine(noise, np.float32([[1, 0, age*19], [0, 1, -age*27]]),
                          (resolution, resolution), borderMode=cv2.BORDER_WRAP)
    yy, xx = np.indices(depth.shape, dtype=np.float32)
    amplitude = size * (.022 + age*.014)
    mx, my = xx+flow[:, :, 0]*amplitude, yy+flow[:, :, 1]*amplitude
    depth = cv2.remap(depth, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    weighted_light = cv2.remap(light_sum, mx, my, cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT)
    associated = np.divide(weighted_light, np.maximum(depth, .001))
    reveal = _smooth(age/.115)
    fade = 1 - _smooth((age-.38)/(duration-.38))
    density = (1.18 if foreground else .75) * reveal * fade
    opacity = np.clip(1-np.exp(-depth*density), 0, .98).astype(np.float32)
    occupied = cv2.findNonZero((opacity > .001).astype(np.uint8))
    if occupied is None:
        return None
    bx, by, bw, bh = cv2.boundingRect(occupied)
    # Include a transparent texel on each side for fringe-free bilinear sampling.
    x0, y0 = max(0, bx-1), max(0, by-1)
    x1, y1 = min(resolution, bx+bw+1), min(resolution, by+bh+1)
    field = cv2.merge((opacity[y0:y1, x0:x1],
                       (associated*opacity)[y0:y1, x0:x1]))
    return field, x0, y0


def render_smoke_layer(frame: np.ndarray, anchor: tuple[int, int, int],
                       age: float, foreground: bool, duration: float) -> None:
    """Render smoke with native-resolution compositing and bounded simulation."""
    if not np.isfinite(age) or not 0 < age < duration:
        return
    cx, cy, size = anchor
    if size <= 0:
        return
    extent = max(8, math.ceil(size*1.60))
    if cx+extent < 0 or cy+extent < 0 or cx-extent >= frame.shape[1] or cy-extent >= frame.shape[0]:
        return
    resolution = min(320, 2*extent+1)
    result = _smoke_field(resolution, float(age), bool(foreground), float(duration))
    if result is None:
        return
    field, bx, by = result
    center = (resolution-1)/2
    scale = (2*extent)/(resolution-1)
    origin_x, origin_y = cx+(bx-center)*scale, cy+(by-center)*scale
    left, top = max(0, math.floor(origin_x)), max(0, math.floor(origin_y))
    right = min(frame.shape[1], math.ceil(origin_x+field.shape[1]*scale))
    bottom = min(frame.shape[0], math.ceil(origin_y+field.shape[0]*scale))
    if left >= right or top >= bottom:
        return
    # Never allocate an enormous upscaled cloud for an off-screen/4K anchor.
    transform = np.float32([[scale, 0, origin_x-left], [0, scale, origin_y-top]])
    sampled = cv2.warpAffine(field, transform, (right-left, bottom-top),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    opacity = sampled[:, :, 0]
    scene = frame[::max(1, frame.shape[0]//24), ::max(1, frame.shape[1]//32)]
    ambient = float(np.mean(scene))/255
    illumination = .75 + .25*math.sqrt(max(0, ambient))
    light = np.clip(sampled[:, :, 1]/np.maximum(opacity, 1e-6)*(255*illumination), 0, 250)
    cloud = cv2.merge(((light*.975).astype(np.uint8), (light*.991).astype(np.uint8),
                       light.astype(np.uint8)))
    destination = frame[top:bottom, left:right]
    cv2.blendLinear(cloud, destination, opacity, 1-opacity, dst=destination)
