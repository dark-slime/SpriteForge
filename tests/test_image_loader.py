from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.image_loader import is_supported_image, load_image, normalize_image_paths


class ImageLoaderTests(unittest.TestCase):
    def test_supported_extensions_are_case_insensitive(self) -> None:
        self.assertTrue(is_supported_image("hero.PNG"))
        self.assertTrue(is_supported_image("icon.WebP"))
        self.assertFalse(is_supported_image("notes.txt"))

    def test_normalize_image_paths_collects_images_from_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "hero.png"
            nested_path = root / "nested" / "icon.webp"
            nested_path.parent.mkdir()

            Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(image_path)
            Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(nested_path)
            (root / "notes.txt").write_text("skip", encoding="utf-8")

            paths = normalize_image_paths([root, image_path])

            self.assertEqual([path.name for path in paths], ["hero.png", "icon.webp"])

    def test_load_image_returns_rgba(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "opaque.jpg"
            Image.new("RGB", (12, 10), (12, 34, 56)).save(image_path)

            image = load_image(image_path)

            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (12, 10))


if __name__ == "__main__":
    unittest.main()
