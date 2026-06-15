from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from core.background_remove import (
    SolidColorRemoveOptions,
    remove_solid_background,
    sample_background_color,
)


class SolidBackgroundRemoveTests(unittest.TestCase):
    def test_remove_solid_background_makes_matching_background_transparent(self) -> None:
        image = Image.new("RGBA", (24, 24), (255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 15, 15), fill=(220, 20, 20, 255))

        result = remove_solid_background(
            image,
            SolidColorRemoveOptions(
                background_color=(255, 255, 255),
                sample_mode="manual",
                tolerance=4,
                feather=0,
                spill_cleanup=0,
            ),
        )

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((10, 10))[3], 255)

    def test_remove_solid_background_feathers_near_background_pixels(self) -> None:
        image = Image.new("RGBA", (3, 1), (255, 255, 255, 255))
        image.putpixel((1, 0), (250, 250, 250, 255))
        image.putpixel((2, 0), (220, 220, 220, 255))

        result = remove_solid_background(
            image,
            SolidColorRemoveOptions(
                background_color=(255, 255, 255),
                sample_mode="manual",
                tolerance=0,
                feather=20,
                spill_cleanup=0,
            ),
        )

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertGreater(result.getpixel((1, 0))[3], 0)
        self.assertLess(result.getpixel((1, 0))[3], 255)
        self.assertEqual(result.getpixel((2, 0))[3], 255)

    def test_sample_background_color_uses_corner_median(self) -> None:
        image = Image.new("RGBA", (32, 32), (241, 242, 243, 255))
        image.putpixel((16, 16), (10, 20, 30, 255))

        self.assertEqual(sample_background_color(image, "corners"), (241, 242, 243))
        self.assertEqual(sample_background_color(image, "top_left"), (241, 242, 243))


if __name__ == "__main__":
    unittest.main()
