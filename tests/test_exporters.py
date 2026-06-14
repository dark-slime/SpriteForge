from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.sprite_slicer import SpriteSlice
from export.json_exporter import export_slices_json
from export.png_exporter import export_processed_image, export_sprites


class ExporterTests(unittest.TestCase):
    def test_export_processed_image_and_sprites_keep_alpha_pngs(self) -> None:
        image = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        image.paste((255, 0, 0, 128), (4, 4, 14, 14))
        slices = [SpriteSlice("sprite_001", 4, 4, 10, 10, 100)]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            processed = export_processed_image(image, output_dir, "source")
            exported = export_sprites(image, slices, output_dir / "sprites")

            self.assertTrue(processed.exists())
            self.assertEqual(len(exported), 1)
            with Image.open(exported[0]) as sprite_image:
                self.assertEqual(sprite_image.mode, "RGBA")
                self.assertEqual(sprite_image.size, (10, 10))
                self.assertEqual(sprite_image.getpixel((0, 0))[3], 128)

    def test_export_slices_json_writes_metadata(self) -> None:
        slices = [SpriteSlice("sprite_001", 12, 8, 16, 20, 320)]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "sprites.json"
            export_slices_json(
                slices,
                output_path,
                source_name="source.png",
                source_size=(128, 64),
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["source"], "source.png")
            self.assertEqual(payload["image_width"], 128)
            self.assertEqual(payload["sprites"][0]["name"], "sprite_001")
            self.assertEqual(payload["sprites"][0]["x"], 12)


if __name__ == "__main__":
    unittest.main()
