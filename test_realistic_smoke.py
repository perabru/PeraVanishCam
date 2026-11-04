"""Texture-compositing regressions independent of camera hardware."""
import unittest

import numpy as np

try:
    from .naruto_effect import EFFECT_SECONDS, _smoke_layer, load_log, overlay_log
    from .realistic_smoke import smoke_resources
except ImportError:
    from naruto_effect import EFFECT_SECONDS, _smoke_layer, load_log, overlay_log
    from realistic_smoke import smoke_resources


class RealisticSmokeTests(unittest.TestCase):
    def test_texture_has_transparency_and_premultiplied_edges(self):
        sprite, _, _ = smoke_resources()
        self.assertEqual(sprite.shape, (384, 384, 4))
        self.assertTrue(np.any(sprite[:, :, 3] == 0))
        self.assertTrue(np.any(sprite[:, :, 3] > .9))
        self.assertTrue(np.all(sprite[:, :, :3] <= sprite[:, :, 3:4]+1e-6))

    def test_screen_edge_clipping_keeps_the_same_cloud(self):
        for foreground in (False, True):
            full = np.full((340, 440, 3), 45, np.uint8)
            _smoke_layer(full, (210, 180, 140), .43, foreground)
            cropped = np.full((180, 160, 3), 45, np.uint8)
            _smoke_layer(cropped, (210-140, 180-80, 140), .43, foreground)
            np.testing.assert_array_equal(cropped, full[80:260, 140:300])

    def test_cloud_does_not_leave_a_dark_rectangle_over_white_video(self):
        frame = np.full((280, 400, 3), 255, np.uint8)
        _smoke_layer(frame, (200, 150, 95), .4, True)
        np.testing.assert_array_equal(frame[:15], np.full_like(frame[:15], 255))
        self.assertGreater(int(frame.min()), 75)
        faded = np.full_like(frame, 255)
        _smoke_layer(faded, (200, 150, 95), EFFECT_SECONDS-.001, True)
        self.assertLess(int(np.max(255-faded)), 2)

    def test_log_exposure_follows_room_and_shadow_stays_local(self):
        sprite = load_log()
        dark, bright = (np.full((240, 400, 3), value, np.uint8) for value in (25, 180))
        for frame in (dark, bright):
            overlay_log(frame, sprite, (200, 185, 110))
        # The same bark receives less light in a dark scene.
        self.assertLess(float(dark[180:205, 180:220].mean()),
                        float(bright[180:205, 180:220].mean()))
        np.testing.assert_array_equal(dark[:30], np.full_like(dark[:30], 25))
        self.assertLess(int(dark[236, 200, 0]), 25)


if __name__ == '__main__':
    unittest.main()
