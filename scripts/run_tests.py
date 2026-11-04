"""Run the upstream tests, whose imports still use the old local_app folder."""
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
package = types.ModuleType("local_app")
package.__path__ = [str(root)]
sys.modules["local_app"] = package
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName("local_app." + name)
    for name in ("test_vanish_cam", "test_video_output", "test_naruto_effect", "test_vanish_sound", "test_anime_jutsus")
)
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
