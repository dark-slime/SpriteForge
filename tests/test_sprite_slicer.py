from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from core.sprite_slicer import SliceOptions, slice_image


class SpriteSlicerTests(unittest.TestCase):
    def test_slice_image_detects_alpha_components_with_padding(self) -> None:
        image = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 31, 31), fill=(255, 0, 0, 255))
        draw.rectangle((80, 12, 111, 43), fill=(0, 255, 0, 255))

        slices = slice_image(
            image,
            SliceOptions(alpha_threshold=10, min_area=64, padding=2),
        )

        self.assertEqual(len(slices), 2)
        self.assertEqual(slices[0].name, "sprite_001")
        self.assertEqual(slices[0].crop_box, (6, 6, 34, 34))
        self.assertEqual(slices[1].crop_box, (78, 10, 114, 46))

    def test_slice_image_filters_small_components(self) -> None:
        image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((1, 1, 2, 2), fill=(255, 255, 255, 255))
        draw.rectangle((10, 10, 21, 21), fill=(255, 255, 255, 255))

        slices = slice_image(
            image,
            SliceOptions(alpha_threshold=10, min_area=16, padding=0),
        )

        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0].crop_box, (10, 10, 22, 22))

    def test_slice_image_uses_file_name_prefix_when_requested(self) -> None:
        image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((4, 4, 9, 9), fill=(255, 255, 255, 255))

        slices = slice_image(
            image,
            SliceOptions(min_area=1, naming_mode="filename"),
            base_name="Hero",
        )

        self.assertEqual(slices[0].name, "Hero_001")


if __name__ == "__main__":
    unittest.main()
