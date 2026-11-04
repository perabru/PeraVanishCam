"""Lightweight color-guided refinement of the segmentation alpha matte.

Only the alpha is filtered. Camera pixels, including faces and clothing detail,
are always left untouched.
"""
from __future__ import annotations

import cv2
import numpy as np


class TemporalPersonMask:
    """Follow motion between inferences and stabilize uncertain alpha edges.

    Optical flow is calculated at at most 256 pixels on the long side. Only
    the alpha history is warped; the current camera image is never filtered.
    New confident foreground/background always wins over history, so a hand
    cannot leave a silhouette behind after the next segmentation inference.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._gray = None
        self._alpha = None
        self._timestamp = None
        self._grid = None
        self._work_grid = None

    def update(self, frame: np.ndarray, new_mask: np.ndarray | None = None,
               timestamp: float | None = None) -> np.ndarray:
        image = np.asarray(frame)
        if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
            raise ValueError('A imagem da camera precisa ter formato HxWx3.')
        height, width = image.shape[:2]
        current = None
        if new_mask is not None:
            current = np.asarray(new_mask, dtype=np.float32)
            if current.ndim == 3 and current.shape[2] == 1:
                current = current[:, :, 0]
            if current.ndim != 2 or min(current.shape) < 1:
                raise ValueError('A mascara precisa ser uma imagem HxW nao vazia.')
            current = np.clip(np.nan_to_num(current, nan=0.0, posinf=1.0,
                                            neginf=0.0), 0, 1)
            if current.shape != (height, width):
                current = cv2.resize(current, (width, height), interpolation=cv2.INTER_LINEAR)
        stamp = None if timestamp is None else float(timestamp)
        expired = (stamp is not None and (not np.isfinite(stamp) or
                   self._timestamp is not None and
                   not 0 < stamp-self._timestamp <= .25))
        if self._alpha is not None and (self._alpha.shape != (height, width) or expired):
            self.reset()

        scale = min(1.0, 256.0/max(height, width))
        work_size = (max(1, round(width*scale)), max(1, round(height*scale)))
        gray = cv2.cvtColor(cv2.resize(image, work_size, interpolation=cv2.INTER_AREA),
                            cv2.COLOR_BGR2GRAY)
        if gray.dtype != np.uint8:
            gray = np.clip(gray, 0, 255).astype(np.uint8)
        if self._alpha is None:
            output = current.copy() if current is not None else np.zeros((height, width), np.float32)
        elif np.array_equal(gray, self._gray):
            if current is None:
                output = self._alpha.copy()
            else:
                uncertain = np.clip(1-np.abs(current-.5)*2, 0, 1)
                uncertain[(current <= .10) | (current >= .90)] = 0
                agreement = np.clip(1-np.abs(current-self._alpha)/.75, 0, 1)
                output = current+.55*uncertain*agreement*(self._alpha-current)
        else:
            # Current -> previous is the inverse map required by remap. A
            # forward flow here would drag a moving outline the wrong way.
            flow = cv2.calcOpticalFlowFarneback(gray, self._gray, None,
                                               .5, 3, 19, 2, 5, 1.1, 0)
            if self._work_grid is None:
                yy, xx = np.indices(gray.shape, dtype=np.float32)
                self._work_grid = (xx, yy)
            mx, my = self._work_grid[0]+flow[:, :, 0], self._work_grid[1]+flow[:, :, 1]
            predicted = cv2.remap(self._gray, mx, my, cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT)
            residual = cv2.absdiff(gray, predicted).astype(np.float32)/255.0
            valid = (mx >= 0) & (my >= 0) & (mx <= gray.shape[1]-1) & (my <= gray.shape[0]-1)
            # A camera cut or abrupt exposure change invalidates all history.
            if float(residual.mean()) > .20:
                output = current.copy() if current is not None else np.zeros((height, width), np.float32)
            else:
                reliability = np.exp(-np.square(residual/.08))*valid
                if current is None:
                    # Between inferences transport the full-resolution matte,
                    # retaining existing fine hair and fingertip coverage.
                    full_flow = cv2.resize(flow, (width, height), interpolation=cv2.INTER_LINEAR)
                    full_flow[:, :, 0] *= width/gray.shape[1]
                    full_flow[:, :, 1] *= height/gray.shape[0]
                    if self._grid is None:
                        yy, xx = np.indices((height, width), dtype=np.float32)
                        self._grid = (xx, yy)
                    previous = cv2.remap(self._alpha, self._grid[0]+full_flow[:, :, 0],
                                          self._grid[1]+full_flow[:, :, 1], cv2.INTER_LINEAR,
                                          borderMode=cv2.BORDER_CONSTANT)
                else:
                    # Fresh native-resolution segmentation supplies detail.
                    # History only damps its uncertain edge, so transport that
                    # guide at flow resolution instead of allocating HD maps.
                    small_alpha = cv2.resize(self._alpha, work_size, interpolation=cv2.INTER_AREA)
                    previous = cv2.remap(small_alpha, mx, my, cv2.INTER_LINEAR,
                                          borderMode=cv2.BORDER_CONSTANT)
                    previous = cv2.resize(previous, (width, height), interpolation=cv2.INTER_LINEAR)
                reliability = cv2.resize(reliability, (width, height), interpolation=cv2.INTER_LINEAR)
                if current is None:
                    # Keep reliable solid pixels fully opaque. Suppress
                    # uncovered/disoccluded areas until fresh inference.
                    output = previous*np.clip((reliability-.05)/.35, 0, 1)
                else:
                    uncertain = np.clip(1-np.abs(current-.5)*2, 0, 1)
                    uncertain[(current <= .10) | (current >= .90)] = 0
                    agreement = np.clip(1-np.abs(current-previous)/.75, 0, 1)
                    history = .55*uncertain*agreement*reliability
                    output = current+history*(previous-current)
        output = np.clip(output, 0, 1).astype(np.float32, copy=False)
        self._gray = gray
        self._alpha = output.copy()
        self._timestamp = stamp if stamp is None or np.isfinite(stamp) else None
        return output


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
