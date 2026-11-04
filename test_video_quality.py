import unittest

import cv2
import numpy as np

try:
    from .video_quality import refine_person_mask
except ImportError:
    from video_quality import refine_person_mask


class MaskQualityTests(unittest.TestCase):
    def test_color_edges_reduce_alpha_bleed_without_filtering_camera_pixels(self):
        # The foreground boundary is sharper than the deliberately blurred
        # model alpha. Refinement should recover the color edge on both sides.
        frame = np.full((96, 160, 3), (30, 30, 30), np.uint8)
        frame[:, 80:] = (190, 210, 230)
        original = frame.copy()
        alpha = np.zeros((96, 160), np.float32)
        alpha[:, 80:] = 1
        blurred = cv2.GaussianBlur(alpha, (0, 0), 3.0)
        refined = refine_person_mask(frame, blurred)
        previous = np.clip((cv2.GaussianBlur(blurred, (0, 0), 2.2) - .12) / .68, 0, 1)
        self.assertLess(refined[:, 78].mean(), previous[:, 78].mean())
        self.assertGreater(refined[:, 81].mean(), previous[:, 81].mean())
        np.testing.assert_array_equal(frame, original)
        self.assertTrue(np.all((refined >= 0) & (refined <= 1)))

    def test_different_colors_with_similar_luminance_still_guide_edges(self):
        frame = np.full((70, 120, 3), (255, 0, 0), np.uint8)
        frame[:, 60:] = (0, 0, 97)  # Both roughly 29 in OpenCV luminance.
        mask = np.zeros((70, 120), np.float32)
        mask[:, 60:] = 1
        blurred = cv2.GaussianBlur(mask, (0, 0), 2)
        guided = refine_person_mask(frame, blurred)
        neutral = refine_person_mask(np.full_like(frame, 90), blurred)
        self.assertLess(guided[:, 58].mean(), neutral[:, 58].mean())
        self.assertGreater(guided[:, 61].mean(), neutral[:, 61].mean())

    def test_low_resolution_masks_are_finite_and_match_hd_camera(self):
        frame = np.full((720, 1280, 3), 90, np.uint8)
        raw = np.zeros((144, 256, 1), np.float32)
        raw[20:130, 100:150] = .95
        raw[0, 0] = np.nan
        raw[0, 1] = np.inf
        raw[0, 2] = -np.inf
        refined = refine_person_mask(frame, raw)
        self.assertEqual(refined.shape, (720, 1280))
        self.assertEqual(refined.dtype, np.float32)
        self.assertTrue(np.isfinite(refined).all())
        self.assertGreater(refined[300, 600], .9)
        self.assertEqual(refined[700, 1200], 0)

    def test_thin_confident_finger_is_kept_without_eroding_or_joining_it(self):
        frame = np.full((90, 140, 3), 120, np.uint8)
        alpha = np.zeros(frame.shape[:2], np.float32)
        alpha[35:85, 55:90] = 1
        alpha[5:40, 65:67] = 1
        refined = refine_person_mask(frame, alpha)
        self.assertTrue(np.all(refined[6:30, 65:67] == 1))
        self.assertTrue(np.all(refined[6:30, 61:63] == 0))

    def test_empty_and_solid_masks_do_not_introduce_phantom_pixels(self):
        frame = np.zeros((51, 79, 3), np.uint8)
        for value in (0, 1):
            with self.subTest(value=value):
                result = refine_person_mask(frame, np.full((3, 7), value, np.float32))
                np.testing.assert_array_equal(result, np.full(frame.shape[:2], value, np.float32))
        single = refine_person_mask(np.zeros((1, 1, 3), np.uint8), np.array([[.5]], np.float32))
        self.assertEqual(single.shape, (1, 1))
        self.assertTrue(np.isfinite(single).all())

    def test_invalid_inputs_raise_clear_errors(self):
        for frame, mask in ((np.zeros((0, 1, 3)), np.zeros((2, 2))),
                            (np.zeros((3, 4)), np.zeros((2, 2))),
                            (np.zeros((3, 4, 3)), np.zeros((2, 2, 2))),
                            (np.zeros((3, 4, 3)), np.zeros((0, 2)))):
            with self.subTest(frame_shape=frame.shape, mask_shape=mask.shape):
                with self.assertRaises(ValueError):
                    refine_person_mask(frame, mask)


if __name__ == '__main__':
    unittest.main()
