from __future__ import annotations

import unittest

from core.slice_editor import clamp_slice, move_slice, renumber_slices, resize_slice
from core.sprite_slicer import SpriteSlice


class SliceEditorTests(unittest.TestCase):
    def test_clamp_slice_keeps_bounds_inside_image(self) -> None:
        sprite_slice = SpriteSlice("sprite_001", -5, 80, 60, 60, 3600)

        clamped = clamp_slice(sprite_slice, (48, 96))

        self.assertEqual(clamped.x, 0)
        self.assertEqual(clamped.y, 80)
        self.assertEqual(clamped.width, 48)
        self.assertEqual(clamped.height, 16)
        self.assertEqual(clamped.area, 768)

    def test_move_slice_clamps_to_image_edges(self) -> None:
        sprite_slice = SpriteSlice("sprite_001", 10, 10, 20, 20, 400)

        moved = move_slice(sprite_slice, 100, -100, (48, 48))

        self.assertEqual(moved.crop_box, (47, 0, 48, 20))

    def test_resize_slice_never_drops_below_one_pixel(self) -> None:
        sprite_slice = SpriteSlice("sprite_001", 10, 10, 20, 20, 400)

        resized = resize_slice(sprite_slice, -100, -100, (48, 48))

        self.assertEqual(resized.width, 1)
        self.assertEqual(resized.height, 1)
        self.assertEqual(resized.area, 1)

    def test_renumber_slices_uses_prefix(self) -> None:
        slices = [
            SpriteSlice("old", 0, 0, 4, 4, 16),
            SpriteSlice("old", 8, 8, 4, 4, 16),
        ]

        renamed = renumber_slices(slices, "Hero")

        self.assertEqual([sprite.name for sprite in renamed], ["Hero_001", "Hero_002"])


if __name__ == "__main__":
    unittest.main()
