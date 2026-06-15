from __future__ import annotations

from dataclasses import replace

from core.sprite_slicer import SpriteSlice


def clamp_slice(sprite_slice: SpriteSlice, image_size: tuple[int, int]) -> SpriteSlice:
    image_width, image_height = image_size
    max_x = max(0, image_width - 1)
    max_y = max(0, image_height - 1)

    x = _clamp(sprite_slice.x, 0, max_x)
    y = _clamp(sprite_slice.y, 0, max_y)
    width = _clamp(sprite_slice.width, 1, max(1, image_width - x))
    height = _clamp(sprite_slice.height, 1, max(1, image_height - y))
    area = width * height
    return replace(sprite_slice, x=x, y=y, width=width, height=height, area=area)


def move_slice(
    sprite_slice: SpriteSlice,
    dx: int,
    dy: int,
    image_size: tuple[int, int],
) -> SpriteSlice:
    moved = replace(sprite_slice, x=sprite_slice.x + dx, y=sprite_slice.y + dy)
    return clamp_slice(moved, image_size)


def resize_slice(
    sprite_slice: SpriteSlice,
    dw: int,
    dh: int,
    image_size: tuple[int, int],
) -> SpriteSlice:
    resized = replace(
        sprite_slice,
        width=sprite_slice.width + dw,
        height=sprite_slice.height + dh,
    )
    return clamp_slice(resized, image_size)


def renumber_slices(slices: list[SpriteSlice], prefix: str) -> list[SpriteSlice]:
    return [
        replace(sprite_slice, name=f"{prefix}_{index:03d}")
        for index, sprite_slice in enumerate(slices, start=1)
    ]


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
