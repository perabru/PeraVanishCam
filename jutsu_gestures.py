"""Two-hand anime seals and a hold/release gate for webcam interaction."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class HandShape:
    points: np.ndarray
    scale: float
    center: np.ndarray
    axis: np.ndarray
    finger_base: np.ndarray
    finger_tip: np.ndarray
    two_fingers: bool
    pair_gap: float


def _shape(landmarks, width: int, height: int) -> HandShape | None:
    if len(landmarks) != 21:
        return None
    p = np.array([(v.x * width, v.y * height) for v in landmarks], dtype=float)
    if not np.isfinite(p).all():
        return None
    scale = max(float(np.linalg.norm(p[5] - p[17])), float(np.linalg.norm(p[0] - p[9])))
    if scale < 7:
        return None
    extended, folded, reaches = [], [], []
    for base in (5, 9, 13, 17):
        finger = p[base:base + 4]
        length = float(np.linalg.norm(np.diff(finger, axis=0), axis=1).sum())
        reach = float(np.linalg.norm(finger[-1] - finger[0]))
        ratio = reach / max(length, 1e-6)
        tip = float(np.linalg.norm(finger[-1] - p[0]))
        pip = float(np.linalg.norm(finger[1] - p[0]))
        extended.append(ratio >= 0.76 and tip > pip * 1.10)
        folded.append(ratio < 0.78 or tip <= pip * 1.08)
        reaches.append(reach)
    reference = min(reaches[:2])
    folded[2] |= reaches[2] < reference * 0.62
    folded[3] |= reaches[3] < reference * 0.62
    finger_base = p[[5, 9]].mean(axis=0)
    finger_tip = p[[8, 12]].mean(axis=0)
    axis = finger_tip - finger_base
    norm = float(np.linalg.norm(axis))
    if norm < scale * 0.3:
        return None
    return HandShape(p, scale, p[[0, 5, 9, 13, 17]].mean(axis=0), axis / norm,
                     finger_base, finger_tip,
                     bool(extended[0] and extended[1] and folded[2] and folded[3]),
                     float(np.linalg.norm(p[8] - p[12])) / scale)


def _cross(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _point_segment_distance(p, a, b) -> float:
    d = b - a
    t = np.clip(np.dot(p - a, d) / max(float(np.dot(d, d)), 1e-8), 0, 1)
    return float(np.linalg.norm(p - (a + t * d)))


def _segments_distance(a, b, c, d) -> float:
    ab, cd = b - a, d - c
    denominator = _cross(ab, cd)
    if abs(denominator) > 1e-8:
        t, u = _cross(c - a, cd) / denominator, _cross(c - a, ab) / denominator
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0
    return min(_point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
               _point_segment_distance(c, a, b), _point_segment_distance(d, a, b))


def classify_hand_seal(hands, width: int, height: int) -> str | None:
    """Crossed two-finger seal -> clones; joined upright two-finger seal -> transform.

    These are geometric approximations adapted to two-hand MediaPipe tracking,
    not a classifier trained to identify every Naruto hand sign.
    """
    if len(hands) != 2:
        return None
    shapes = [_shape(hand, width, height) for hand in hands]
    if any(s is None for s in shapes):
        return None
    a, b = shapes
    if not (a.two_fingers and b.two_fingers) or max(a.scale, b.scale) > min(a.scale, b.scale) * 2:
        return None
    size = (a.scale + b.scale) * 0.5
    if np.linalg.norm(a.center - b.center) > size * 3.2:
        return None
    alignment = float(np.dot(a.axis, b.axis))
    tip_distance = float(np.linalg.norm(a.finger_tip - b.finger_tip))
    if (abs(alignment) < 0.58 and tip_distance < size * 1.7
            and _segments_distance(a.finger_base, a.finger_tip, b.finger_base, b.finger_tip) < size * 0.42):
        return "clones"
    if (alignment > 0.74 and tip_distance < size * 0.95
            and max(a.pair_gap, b.pair_gap) < 0.55):
        return "transform"
    return None


@dataclass
class SealGate:
    hold_seconds: float = 0.65
    release_seconds: float = 0.30
    tolerance_seconds: float = 0.18
    cooldown_seconds: float = 1.1
    candidate: str | None = None
    since: float = 0.0
    missing_since: float | None = None
    armed: bool = True
    cooldown_until: float = 0.0

    def disarm(self, now: float) -> None:
        self.armed = False
        self.candidate = None
        self.missing_since = None
        self.cooldown_until = now + self.cooldown_seconds

    def update(self, sign: str | None, now: float) -> str | None:
        if sign is None:
            if self.missing_since is None:
                self.missing_since = now
            gap = now - self.missing_since
            if gap >= self.tolerance_seconds:
                self.candidate = None
            if gap >= self.release_seconds:
                self.armed = True
            return None
        if self.missing_since is not None and now - self.missing_since > self.tolerance_seconds:
            self.candidate = None
        self.missing_since = None
        if not self.armed or now < self.cooldown_until:
            return None
        if sign != self.candidate:
            self.candidate, self.since = sign, now
            return None
        if now - self.since >= self.hold_seconds:
            self.armed = False
            self.cooldown_until = now + self.cooldown_seconds
            return sign
        return None
