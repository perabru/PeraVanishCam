import unittest

import cv2
import numpy as np

try:
    from .video_quality import TemporalPersonMask, refine_person_mask
except ImportError:
    from video_quality import TemporalPersonMask, refine_person_mask


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


class TemporalMaskTests(unittest.TestCase):
    @staticmethod
    def scene():
        rng = np.random.default_rng(16)
        frame = np.full((96, 160, 3), 20, np.uint8)
        frame[20:88, 45:85] = rng.integers(100, 240, (68, 40, 3), dtype=np.uint8)
        mask = np.zeros(frame.shape[:2], np.float32)
        mask[20:88, 45:85] = 1
        return frame, mask

    def test_static_uncertain_edge_jitter_is_reduced_without_changing_camera(self):
        frame, solid = self.scene()
        original = frame.copy()
        stabilizer = TemporalPersonMask()
        noisy = solid.copy()
        noisy[20:88, 45:48] = .4
        first = stabilizer.update(frame, noisy, timestamp=0)
        noisy[20:88, 45:48] = .6
        second = stabilizer.update(frame, noisy, timestamp=1/30)
        self.assertLess(np.abs(second[20:88, 45:48]-first[20:88, 45:48]).mean(), .15)
        np.testing.assert_array_equal(second[20:88, 50:85], solid[20:88, 50:85])
        np.testing.assert_array_equal(second[:10], solid[:10])
        np.testing.assert_array_equal(frame, original)
        self.assertTrue(np.all(noisy[20:88, 45:48] == .6))

    def test_inverse_flow_moves_mask_with_person_between_inferences(self):
        frame, mask = self.scene()
        stabilizer = TemporalPersonMask()
        stabilizer.update(frame, mask, timestamp=0)
        affine = np.float32([[1, 0, 6], [0, 1, 0]])
        moved = cv2.warpAffine(frame, affine, (160, 96), borderValue=(20, 20, 20))
        expected = cv2.warpAffine(mask, affine, (160, 96))
        tracked = stabilizer.update(moved, timestamp=1/30)
        self.assertLess(np.abs(tracked-expected).mean(), np.abs(mask-expected).mean()*.45)
        self.assertGreater(tracked[40:70, 87:90].mean(), .85)
        self.assertLess(tracked[40:70, 45:48].mean(), .15)

    def test_confident_new_segmentation_removes_old_hand_immediately(self):
        frame, mask = self.scene()
        stabilizer = TemporalPersonMask()
        stabilizer.update(frame, mask, timestamp=0)
        current = mask.copy()
        current[20:40, 45:55] = 0
        current[2:15, 100:103] = 1
        result = stabilizer.update(frame, current, timestamp=1/30)
        np.testing.assert_array_equal(result, current)

    def test_cuts_gaps_and_resets_do_not_reuse_an_old_silhouette(self):
        frame, mask = self.scene()
        stabilizer = TemporalPersonMask()
        stabilizer.update(frame, mask, timestamp=0)
        cut = np.full_like(frame, 250)
        np.testing.assert_array_equal(stabilizer.update(cut, timestamp=1/30), np.zeros_like(mask))
        stabilizer.update(frame, mask, timestamp=2/30)
        np.testing.assert_array_equal(stabilizer.update(frame, timestamp=1), np.zeros_like(mask))
        stabilizer.update(frame, mask, timestamp=2)
        stabilizer.reset()
        np.testing.assert_array_equal(stabilizer.update(frame), np.zeros_like(mask))
        result = stabilizer.update(np.zeros((9, 13, 3), np.uint8), np.ones((3, 5), np.float32))
        np.testing.assert_array_equal(result, np.ones((9, 13), np.float32))

    def test_nonfinite_masks_and_returned_arrays_do_not_poison_history(self):
        frame, mask = self.scene()
        raw = mask.copy()
        raw[0, :3] = [np.nan, np.inf, -np.inf]
        stabilizer = TemporalPersonMask()
        result = stabilizer.update(frame, raw)
        self.assertTrue(np.isfinite(result).all())
        self.assertEqual(result.dtype, np.float32)
        result.fill(0)
        tracked = stabilizer.update(frame)
        self.assertGreater(tracked[40:70, 55:75].mean(), .99)
        self.assertTrue(np.isnan(raw[0, 0]))


if __name__ == '__main__':
    unittest.main()
