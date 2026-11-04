"""Geometry, visual compositing and camera-output regression tests for anime jutsus."""
import argparse
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from local_app import anime_effects as effects
from local_app import ninja_runtime as runtime
from local_app.jutsu_gestures import classify_hand_seal, SealGate
from local_app.naruto_effect import EFFECT_SECONDS, load_log, render_substitution, substitution_anchor


def hand(cx=300, cy=300, angle=0, gap=.12, open_palm=False):
    p = np.zeros((21, 2)); p[0] = (0, 1)
    for j, base in enumerate((5, 9, 13, 17)):
        x = (j-1.5)*.28
        if j < 2:
            x = -gap/2 if j == 0 else gap/2
        if j < 2 or open_palm:
            p[base:base+4] = [(x, 0), (x, -.42), (x, -.84), (x, -1.25)]
        else:
            p[base:base+4] = [(x, 0), (x, -.35), (x+.06, -.2), (x+.1, .10)]
    a = np.radians(angle)
    p = p @ np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]).T * 65 + (cx, cy)
    return [SimpleNamespace(x=x/640, y=y/480) for x, y in p]


class SealTests(unittest.TestCase):
    def test_cross_and_tiger_are_distinct_under_rotation_scale_and_mirror(self):
        poses = [('clones', [hand(), hand(245, 245, 90)]),
                 ('substitution', [hand(), hand(345, 300)])]
        for expected, pair in poses:
            for angle in (0, .45, 1.4, 2.8):
                for scale in (.6, 1.2):
                    for mirror in (-1, 1):
                        transformed = []
                        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                        for points in pair:
                            p = np.array([(v.x*640, v.y*480) for v in points])-(320, 240)
                            p[:, 0] *= mirror
                            p = p @ rotation.T * scale + (320, 240)
                            transformed.append([SimpleNamespace(x=x/640, y=y/480) for x, y in p])
                        with self.subTest(expected=expected, angle=angle, scale=scale, mirror=mirror):
                            self.assertEqual(classify_hand_seal(transformed, 640, 480), expected)

    def test_missing_open_separated_and_invalid_hands_do_not_trigger(self):
        pairs = [[], [hand()], [hand(open_palm=True), hand(345, 300, open_palm=True)],
                 [hand(), hand(600, 100, 90)], [hand(gap=1.5), hand(345, 300, gap=1.5)],
                 [hand()[:20], hand(345, 300)]]
        invalid = hand(); invalid[8].x = float('nan'); pairs.append([invalid, hand()])
        for pair in pairs:
            self.assertIsNone(classify_hand_seal(pair, 640, 480))

    def test_hold_releases_and_cooldown_prevent_repeated_triggers(self):
        gate = SealGate()
        for now in (0, .3, .64):
            self.assertIsNone(gate.update('clones', now))
        self.assertEqual(gate.update('clones', .66), 'clones')
        self.assertIsNone(gate.update('clones', 1.9))
        self.assertIsNone(gate.update(None, 2.0))
        self.assertIsNone(gate.update(None, 2.35))
        self.assertIsNone(gate.update('substitution', 2.4))
        self.assertEqual(gate.update('substitution', 3.06), 'substitution')

    def test_brief_detection_dropout_is_tolerated_but_a_long_gap_resets_hold(self):
        gate = SealGate()
        gate.update('clones', 0); gate.update('clones', .35)
        gate.update(None, .45); gate.update('clones', .55)
        self.assertEqual(gate.update('clones', .67), 'clones')
        gate = SealGate()
        gate.update('clones', 0); gate.update(None, .3)
        self.assertIsNone(gate.update('clones', .7))
        self.assertIsNone(gate.update('clones', .9))


class EffectTests(unittest.TestCase):
    @staticmethod
    def scene():
        background = np.full((160, 240, 3), 30, np.uint8)
        frame = background.copy(); frame[20:150, 93:147] = (50, 100, 205)
        mask = np.zeros((160, 240), np.float32); mask[20:150, 93:147] = 1
        return frame, background, mask

    def test_clones_create_three_separate_live_silhouettes(self):
        frame, background, mask = self.scene()
        out = effects.render_clones(frame, background, mask, 2)
        count, _, stats, centroids = cv2.connectedComponentsWithStats((out[:, :, 2] > 100).astype(np.uint8))
        visible = sorted(centroids[i, 0] for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] > 100)
        self.assertEqual(len(visible), 3)
        self.assertLess(visible[0], 70); self.assertGreater(visible[-1], 170)
        changed = frame.copy(); changed[mask > .5] = (210, 80, 40)
        live = effects.render_clones(changed, background, mask, 2)
        self.assertTrue(np.any(live[:, :70] != out[:, :70]))
        self.assertTrue(np.any(live[:, 170:] != out[:, 170:]))
        np.testing.assert_array_equal(out[0, 0], background[0, 0])

    def test_substitution_removes_person_and_leaves_log_after_smoke(self):
        frame, background, mask = self.scene()
        out = render_substitution(frame, background, mask, load_log(), substitution_anchor(mask), 2)
        self.assertEqual(out.shape, frame.shape)
        self.assertEqual(out.dtype, np.uint8)
        self.assertFalse(np.array_equal(out, frame))
        self.assertFalse(np.array_equal(out, background))
        np.testing.assert_array_equal(out[0, 0], background[0, 0])
        self.assertFalse(np.any(np.all(out == (50, 100, 205), axis=2)))

    def test_empty_mask_keeps_live_camera_in_clone_mode(self):
        frame, background, mask = self.scene(); mask[:] = 0
        np.testing.assert_array_equal(effects.render_clones(frame, background, mask, 2), frame)

    def test_smoke_finishes_and_help_does_not_modify_video(self):
        frame, background, mask = self.scene()
        early = effects.render_clones(frame, background, mask, .3)
        late = effects.render_clones(frame, background, mask, 2)
        self.assertFalse(np.array_equal(early, late))
        self.assertEqual(runtime.gesture_help().shape, (470, 820, 3))
        state = runtime.NinjaState(); state.activate('substitution', 1); state.reset()
        self.assertIsNone(state.active)
        self.assertEqual(state.selected, 'substitution')


class CameraTests(unittest.TestCase):
    def test_cross_and_tiger_trigger_clones_and_persistent_log_in_virtual_output(self):
        frame, background, mask = EffectTests.scene()
        capture, segmenter, tracker = Mock(), Mock(), Mock()
        capture.read.side_effect = [(True, f.copy()) for f in [background]*2+[frame]*8]
        tracker.recognize_seal.side_effect = ['clones', 'clones', None, None,
                                             'substitution', 'substitution', None, None]
        virtual, sound, sent = Mock(), Mock(), []
        api = SimpleNamespace(download_models=Mock(), open_camera=Mock(return_value=capture),
                              create_tasks=Mock(return_value=(segmenter, tracker)),
                              open_virtual_camera=Mock(return_value=virtual),
                              person_mask=Mock(return_value=mask),
                              send_virtual_frame=lambda camera, image: sent.append(image.copy()),
                              set_fullscreen=Mock(), WINDOW_NAME='test', CALIBRATION_SECONDS=4,
                              BACKGROUND_SAMPLE_SECONDS=.55,
                              mp=SimpleNamespace(Image=Mock(), ImageFormat=SimpleNamespace(SRGB='RGB')))
        args = argparse.Namespace(camera=0, width=240, height=160, fps=30, fullscreen=False,
                                  no_mirror=True, gesture_debug=False, sound=None)
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(runtime.time, 'perf_counter', side_effect=[
                0, 0, 4.1, 4.3, 5.01, 5.2, 5.6, 6.2, 6.91,
                6.91+EFFECT_SECONDS+.1, 6.91+EFFECT_SECONDS+.3]))
            for name in ('namedWindow', 'resizeWindow', 'destroyAllWindows', 'imshow'):
                mocks.enter_context(patch.object(runtime.cv2, name))
            mocks.enter_context(patch.object(runtime.cv2, 'getWindowProperty', return_value=1))
            mocks.enter_context(patch.object(runtime.cv2, 'waitKey', side_effect=[0]*9+[ord('q')]))
            mocks.enter_context(patch.object(runtime, 'VanishSound', return_value=sound))
            mocks.enter_context(patch('builtins.print'))
            with ExitStack() as resources:
                self.assertEqual(runtime.run_ninja_camera(args, resources, 'clones', api), 0)
        self.assertEqual(sound.play.call_count, 2)
        self.assertFalse(np.array_equal(sent[4], frame))
        final_log = render_substitution(frame, background, mask, load_log(), substitution_anchor(mask), 2)
        np.testing.assert_array_equal(sent[-1], final_log)
        self.assertFalse(np.any(np.all(sent[-1] == (50, 100, 205), axis=2)))
        capture.release.assert_called_once()
        virtual.close.assert_called_once()

    def exercise(self, fail=False):
        frame, background, mask = EffectTests.scene()
        capture, segmenter, tracker = Mock(), Mock(), Mock()
        tracker.recognize_seal.return_value = None
        capture.read.side_effect = [(True, f.copy()) for f in [background, background]+[frame]*6]
        virtual, sound = Mock(), Mock()
        displayed, sent = [], []
        def send(camera, image):
            if fail:
                raise RuntimeError('test sink failed')
            sent.append(image.copy())
        api = SimpleNamespace(download_models=Mock(), open_camera=Mock(return_value=capture),
                              create_tasks=Mock(return_value=(segmenter, tracker)),
                              open_virtual_camera=Mock(return_value=virtual),
                              person_mask=Mock(return_value=mask), send_virtual_frame=send,
                              set_fullscreen=Mock(), WINDOW_NAME='test', CALIBRATION_SECONDS=4,
                              BACKGROUND_SAMPLE_SECONDS=.55,
                              mp=SimpleNamespace(Image=Mock(), ImageFormat=SimpleNamespace(SRGB='RGB')))
        args = argparse.Namespace(camera=0, width=240, height=160, fps=30, fullscreen=False,
                                  no_mirror=True, gesture_debug=False, sound=None)
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(runtime.time, 'perf_counter', side_effect=[0, 0, 4.1, 4.3, 4.6, 4.8, 5.3, 5.5, 5.7]))
            for name in ('namedWindow', 'resizeWindow', 'destroyAllWindows'):
                mocks.enter_context(patch.object(runtime.cv2, name))
            mocks.enter_context(patch.object(runtime.cv2, 'getWindowProperty', return_value=1))
            mocks.enter_context(patch.object(runtime.cv2, 'imshow', side_effect=lambda name, image: displayed.append(image.copy())))
            mocks.enter_context(patch.object(runtime.cv2, 'waitKey', side_effect=[0, ord('c'), 0, ord('t'), 0, ord('r'), 0, ord('q')]))
            mocks.enter_context(patch.object(runtime, 'VanishSound', return_value=sound))
            mocks.enter_context(patch('builtins.print'))
            with ExitStack() as resources:
                if fail:
                    with self.assertRaisesRegex(RuntimeError, 'test sink failed'):
                        runtime.run_ninja_camera(args, resources, 'clones', api)
                else:
                    self.assertEqual(runtime.run_ninja_camera(args, resources, 'clones', api), 0)
        capture.release.assert_called_once(); segmenter.close.assert_called_once()
        tracker.close.assert_called_once(); virtual.close.assert_called_once(); sound.close.assert_called_once()
        if not fail:
            self.assertEqual(len(sent), 8)
            for a, b in zip(sent, displayed): np.testing.assert_array_equal(a, b)
            self.assertFalse(np.array_equal(sent[2], frame))
            self.assertFalse(np.array_equal(sent[4], frame))
            np.testing.assert_array_equal(sent[6], frame)
            self.assertEqual(sound.play.call_count, 2)

    def test_live_keyboard_effects_reach_preview_and_virtual_camera_and_reset(self):
        self.exercise()

    def test_devices_close_on_virtual_output_failure(self):
        self.exercise(fail=True)


if __name__ == '__main__':
    unittest.main()
