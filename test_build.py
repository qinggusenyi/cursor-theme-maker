import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.build import ROLES, build, build_macos


class BuildTest(unittest.TestCase):
    def test_complete_package_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            states = {}
            for index, state in enumerate(ROLES):
                image = Image.new("RGBA", (400, 400))
                ImageDraw.Draw(image).ellipse((40, 40, 360, 360), fill=(index * 13, 180, 20, 255))
                image.save(root / "source" / f"{state}.png")
                states[state] = {"file": f"source/{state}.png", "hotspot": [200, 200]}
            manifest = root / "theme.json"
            manifest.write_text(json.dumps({"name": "Test", "states": states}), encoding="utf-8")
            package = build(manifest, root / "theme")
            self.assertEqual(len(list((root / "theme").glob("*.cur"))), 15)
            with zipfile.ZipFile(package) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 21)
            mac_package = build_macos(manifest, root / "macos")
            with zipfile.ZipFile(mac_package) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(len(archive.namelist()), 17)
                self.assertTrue(any(name.endswith("README-macOS.md") for name in archive.namelist()))
                self.assertFalse(any(name.endswith(".cmd") for name in archive.namelist()))
            states["help"]["file"] = states["normal"]["file"]
            manifest.write_text(json.dumps({"name": "Test", "states": states}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reused"):
                build(manifest, root / "duplicate")
            self.assertFalse((root / "duplicate").exists())


if __name__ == "__main__":
    unittest.main()
