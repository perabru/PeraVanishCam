"""Regression coverage for alpha scaling and the live clone image quality."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import cv2
import numpy as np

try:
    from . import anime_effects as effects
except ImportError:
    import anime_effects as effects


class CloneQualityTests(unittest.TestCase):
    @staticmethod
    def scene(width=360, height=240):
        background = np.full((height, width, 3), (42, 47, 51), np.uint8)
        frame = background.copy()
        mask = np.zeros((height, width), np.float32)
        x0, x1, y0, y1 = width*42//100, width*58//100, height//8, height*15//16
        mask[y0:y1, x0:x1] = 1
        yy, xx = np.indices((y1-y0, x1-x0))
        frame[y0:y1, x0:x1, 0] = (xx*7+yy*3)%180+50
        frame[y0:y1, x0:x1, 1] = 110
        frame[y0:y1, x0:x1, 2] = (xx*3+yy*2)%160+80
        return frame, background, mask

    def test_premultiplied_resize_excludes_hidden_background_colors(self):
        # Invisible red pixels used to leak into blue edges during resize.
        rgb = np.full((8, 8, 3), (0, 0, 255), np.uint8)
        alpha = np.zeros((8, 8), np.float32)
        rgb[2:6, 2:6] = (220, 80, 10)
        alpha[2:6, 2:6] = 1
        color, coverage = effects._resize_cutout(rgb, alpha, (3, 3))
        np.testing.assert_allclose(color[:, :, 2], coverage*10, atol=.0001)
        np.testing.assert_allclose(color[:, :, 0], coverage*220, atol=.0001)
        target = np.full((3, 3, 3), 30, np.uint8)
        effects._paste_premultiplied(target, color, coverage, 0, 0)
        expected = np.rint(color+30*(1-coverage[:, :, None])).astype(np.uint8)
        np.testing.assert_array_equal(target, expected)

    def test_clones_and_original_remain_live_with_native_center_details(self):
        frame, background, mask = self.scene()
        result = effects.render_clones(frame, background, mask, effects.BURST_SECONDS+1)
        np.testing.assert_array_equal(result[mask == 1], frame[mask == 1])
        changed = frame.copy()
        changed[mask == 1] = (80, 220, 40)
        live = effects.render_clones(changed, background, mask, effects.BURST_SECONDS+1)
        self.assertGreater(np.count_nonzero(result[:, :120] != live[:, :120]), 200)
        self.assertGreater(np.count_nonzero(result[:, 240:] != live[:, 240:]), 200)
        # Neither source nor calibrated background may be modified in place.
        self.assertTrue(np.all(background == (42, 47, 51)))
        self.assertFalse(np.array_equal(frame[mask == 1], changed[mask == 1]))

    def test_bounds_include_detached_hands_but_skip_distant_noise(self):
        mask = np.zeros((180, 260), np.float32)
        mask[30:170, 100:140] = 1
        mask[10:25, 145:160] = .8
        mask[0:3, 0:3] = 1
        self.assertEqual(effects.person_bounds(mask), (100, 10, 60, 160))

    def test_empty_or_nonfinite_mask_does_not_replace_live_frame(self):
        frame, background, mask = self.scene()
        mask.fill(0)
        mask[0, 0] = np.nan
        mask[-1, -1] = np.inf
        np.testing.assert_array_equal(effects.render_clones(frame, background, mask, 1), frame)

    def test_smoke_wraps_each_clone_and_finishes(self):
        frame, background, mask = self.scene()
        with patch.object(effects, '_smoke_layer') as smoke:
            effects.render_clones(frame, background, mask, .4)
            self.assertEqual(smoke.call_count, 4)
            anchors = [call.args[1] for call in smoke.call_args_list]
            self.assertEqual(len(set(anchors)), 2)
            self.assertEqual([call.args[3] for call in smoke.call_args_list], [False, False, True, True])
            smoke.reset_mock()
            effects.render_clones(frame, background, mask, effects.BURST_SECONDS)
            smoke.assert_not_called()

    def test_clipping_premultiplied_sprite_never_wraps_or_brightens_background(self):
        target = np.full((4, 4, 3), 20, np.uint8)
        color = np.full((4, 4, 3), 70, np.float32)
        alpha = np.ones((4, 4), np.float32)*.5
        effects._paste_premultiplied(target, color, alpha, -2, -2)
        np.testing.assert_array_equal(target[:2, :2], np.full((2, 2, 3), 80, np.uint8))
        np.testing.assert_array_equal(target[2:], np.full((2, 4, 3), 20, np.uint8))
        untouched = target.copy()
        effects._paste_premultiplied(target, color, alpha, 40, 40)
        np.testing.assert_array_equal(target, untouched)

    def test_hd_output_keeps_resolution_and_clear_background_after_smoke(self):
        frame, background, mask = self.scene(1280, 720)
        result = effects.render_clones(frame, background, mask, 2)
        self.assertEqual(result.shape, (720, 1280, 3))
        self.assertEqual(result.dtype, np.uint8)
        np.testing.assert_array_equal(result[:20], background[:20])
        np.testing.assert_array_equal(result[mask == 1], frame[mask == 1])
        self.assertGreater(cv2.countNonZero(cv2.cvtColor(cv2.absdiff(result, background), cv2.COLOR_BGR2GRAY)), np.count_nonzero(mask))


if __name__ == '__main__':
    unittest.main()
