from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image


NamingMode = Literal["sprite", "filename"]


class SpriteSlicerDependencyError(RuntimeError):
    """Raised when OpenCV or NumPy is not installed."""


@dataclass(slots=True)
class SliceOptions:
    alpha_threshold: int = 10
    min_area: int = 64
    padding: int = 4
    merge_nearby: bool = False
    naming_mode: NamingMode = "sprite"


@dataclass(slots=True)
class SpriteSlice:
    name: str
    x: int
    y: int
    width: int
    height: int
    area: int

    @property
    def crop_box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_json(self) -> dict[str, int | str]:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def slice_image(
    image: Image.Image,
    options: SliceOptions | None = None,
    base_name: str | None = None,
) -> list[SpriteSlice]:
    options = options or SliceOptions()
    rgba_image = image.convert("RGBA")
    image_width, image_height = rgba_image.size

    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise SpriteSlicerDependencyError(
            "OpenCV and NumPy are required for automatic slicing. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    alpha = np.asarray(rgba_image)[:, :, 3]
    mask = (alpha > _clamp(options.alpha_threshold, 0, 255)).astype("uint8")

    if not mask.any():
        return []

    detection_mask = mask
    if options.merge_nearby:
        kernel_size = max(3, options.padding * 2 + 1)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        detection_mask = cv2.dilate(mask, kernel, iterations=1)

    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        detection_mask,
        connectivity=8,
    )

    boxes: list[tuple[int, int, int, int, int]] = []
    for component_index in range(1, component_count):
        area = int(stats[component_index, cv2.CC_STAT_AREA])
        if area < max(0, options.min_area):
            continue

        x = int(stats[component_index, cv2.CC_STAT_LEFT])
        y = int(stats[component_index, cv2.CC_STAT_TOP])
        width = int(stats[component_index, cv2.CC_STAT_WIDTH])
        height = int(stats[component_index, cv2.CC_STAT_HEIGHT])

        left = max(0, x - options.padding)
        top = max(0, y - options.padding)
        right = min(image_width, x + width + options.padding)
        bottom = min(image_height, y + height + options.padding)

        boxes.append((left, top, right - left, bottom - top, area))

    boxes.sort(key=lambda item: (item[1], item[0]))
    prefix = _name_prefix(options.naming_mode, base_name)

    return [
        SpriteSlice(
            name=f"{prefix}_{index:03d}",
            x=x,
            y=y,
            width=width,
            height=height,
            area=area,
        )
        for index, (x, y, width, height, area) in enumerate(boxes, start=1)
    ]


def _name_prefix(naming_mode: NamingMode, base_name: str | None) -> str:
    if naming_mode == "filename" and base_name:
        return base_name
    return "sprite"


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
