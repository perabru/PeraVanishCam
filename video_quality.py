"""Lightweight color-guided refinement of the segmentation alpha matte.

Only the alpha is filtered. Camera pixels, including faces and clothing detail,
are always left untouched.
"""
from __future__ import annotations

import cv2
import numpy as np


def refine_person_mask(frame: np.ndarray, raw_mask: np.ndarray) -> np.ndarray:
    """Return a finite float32 HxW alpha using the frame's color edges.

    ``frame`` is the current uint8 BGR/RGB camera image. ``raw_mask`` is a
    confidence map at any nonempty resolution, optionally HxWx1. A bounded
    512-pixel working image supplies local color/alpha coefficients; evaluating
    those at camera resolution keeps edges sharper than a full-frame blur.
    Confident thin structures are retained rather than removed by erosion.
    """
    image = np.asarray(frame)
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
        raise ValueError('A imagem da camera precisa ter formato HxWx3.')
    raw = np.asarray(raw_mask, dtype=np.float32)
    if raw.ndim == 3 and raw.shape[2] == 1:
        raw = raw[:, :, 0]
    if raw.ndim != 2 or min(raw.shape) < 1:
        raise ValueError('A mascara precisa ser uma imagem HxW nao vazia.')
    raw = np.nan_to_num(raw, nan=0.0, posinf=1.0, neginf=0.0)
    raw = np.clip(raw, 0.0, 1.0)
    height, width = image.shape[:2]
    # Exact fast paths avoid inventing a silhouette in an empty mask.
    if not np.any(raw):
        return np.zeros((height, width), np.float32)
    if np.all(raw == 1.0):
        return np.ones((height, width), np.float32)
    alpha = cv2.resize(raw, (width, height), interpolation=cv2.INTER_LINEAR)
    scale = min(1.0, 512.0 / max(width, height))
    work_width = max(1, round(width * scale))
    work_height = max(1, round(height * scale))
    work_size = (work_width, work_height)
    guide = cv2.resize(image, work_size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    confidence = cv2.resize(raw, work_size, interpolation=cv2.INTER_LINEAR)
    radius = max(2, round(max(work_size) / 160))
    kernel = (2 * radius + 1, 2 * radius + 1)

    def mean(values):
        return cv2.boxFilter(values, -1, kernel, normalize=True, borderType=cv2.BORDER_REFLECT)

    mean_guide = mean(guide)
    mean_confidence = mean(confidence)
    # A local color axis follows the complete RGB/BGR difference across an
    # edge, including different colors with the same luminance. Using the
    # covariance trace keeps the solve stable in flat/noisy webcam regions.
    channel_sum = np.ones((1, 3), np.float32)
    variance = cv2.transform(np.maximum(mean(guide * guide) - mean_guide * mean_guide, 0), channel_sum)
    covariance = mean(guide * confidence[:, :, None]) - mean_guide * mean_confidence[:, :, None]
    a = covariance / (variance[:, :, None] + .0025)
    b = mean_confidence - cv2.transform(a * mean_guide, channel_sum)
    a = cv2.resize(mean(a), (width, height), interpolation=cv2.INTER_LINEAR)
    b = cv2.resize(mean(b), (width, height), interpolation=cv2.INTER_LINEAR)
    refined = b + cv2.transform(cv2.multiply(a, image, scale=1.0/255.0, dtype=cv2.CV_32F), channel_sum)
    # Never erase a confident fingertip/hair strand simply because its local
    # support is thin. The uncertain edge is free to follow the image colors.
    certainty = np.clip((np.abs(alpha - .5) - .30) * 5.0, 0.0, 1.0)
    refined += certainty * (alpha - refined)
    # A narrow soft transition removes weak background haze without a hard
    # binary cutout, preserving intermediate alpha along hair and fingers.
    return np.clip((refined - .10) / .80, 0.0, 1.0).astype(np.float32, copy=False)
