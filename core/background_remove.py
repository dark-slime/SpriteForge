from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageFilter


ColorSampleMode = Literal["corners", "top_left", "manual"]
RemoveScopeMode = Literal["edge_connected", "global", "seed"]


class BackgroundRemoveUnavailable(RuntimeError):
    """Raised when required image processing dependencies are unavailable."""


@dataclass(slots=True)
class SolidColorRemoveOptions:
    background_color: tuple[int, int, int] | None = None
    sample_mode: ColorSampleMode = "corners"
    remove_scope: RemoveScopeMode = "edge_connected"
    seed_points: tuple[tuple[int, int], ...] = ()
    tolerance: int = 28
    feather: int = 10
    spill_cleanup: int = 60
    edge_contract: int = 0


def sample_background_color(
    image: Image.Image,
    mode: ColorSampleMode = "corners",
) -> tuple[int, int, int]:
    rgba_image = image.convert("RGBA")
    width, height = rgba_image.size

    if mode == "top_left":
        red, green, blue, _alpha = rgba_image.getpixel((0, 0))
        return (red, green, blue)

    try:
        import numpy as np
    except ImportError as exc:
        raise BackgroundRemoveUnavailable(
            "NumPy is required for solid color background removal. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    arr = np.asarray(rgba_image)
    sample_size = max(2, min(16, min(width, height) // 24 or 2))
    corner_blocks = [
        arr[:sample_size, :sample_size, :3],
        arr[:sample_size, width - sample_size :, :3],
        arr[height - sample_size :, :sample_size, :3],
        arr[height - sample_size :, width - sample_size :, :3],
    ]
    samples = np.concatenate([block.reshape(-1, 3) for block in corner_blocks], axis=0)
    color = np.median(samples, axis=0)
    return tuple(int(channel) for channel in color)


def remove_solid_background(
    image: Image.Image,
    options: SolidColorRemoveOptions | None = None,
) -> Image.Image:
    options = options or SolidColorRemoveOptions()
    rgba_image = image.convert("RGBA")

    try:
        import numpy as np
    except ImportError as exc:
        raise BackgroundRemoveUnavailable(
            "NumPy is required for solid color background removal. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    background_color = options.background_color
    if background_color is None or options.sample_mode != "manual":
        background_color = sample_background_color(rgba_image, options.sample_mode)

    arr = np.asarray(rgba_image).astype("float32")
    rgb = arr[:, :, :3]
    original_alpha = arr[:, :, 3]

    bg = np.asarray(background_color, dtype="float32")
    color_delta = np.abs(rgb - bg)
    distance = np.max(color_delta, axis=2)
    tolerance = _clamp(options.tolerance, 0, 255)
    feather = _clamp(options.feather, 0, 255)
    cleanup_strength = (_clamp(options.spill_cleanup, 0, 100) / 100.0) ** 0.5

    if feather <= 0:
        keep = (distance > tolerance).astype("float32")
    else:
        keep = np.clip((distance - tolerance) / feather, 0.0, 1.0)
        keep = keep * keep * (3.0 - 2.0 * keep)

    hard_background = distance <= tolerance
    selected_background_mask = _selected_background_mask(
        hard_background,
        options.remove_scope,
        options.seed_points,
    )
    if options.remove_scope != "global":
        scope_mask = _soft_scope_mask(selected_background_mask, feather)
        keep = np.where(scope_mask, keep, 1.0)

    channel_ranges = np.maximum(bg, 255.0 - bg)
    channel_ranges = np.maximum(channel_ranges, 1.0)
    matte_alpha = np.max(color_delta / channel_ranges, axis=2)
    tolerance_fraction = tolerance / 255.0
    matte_alpha = np.clip(
        (matte_alpha - tolerance_fraction) / max(1.0 - tolerance_fraction, 1.0 / 255.0),
        0.0,
        1.0,
    )

    edge_band = np.zeros_like(keep, dtype="float32")
    if cleanup_strength > 0:
        edge_band = _edge_band_mask(
            selected_background_mask,
            radius=max(1, min(4, feather // 16 + 1)),
        )
        defringed_keep = np.minimum(keep, matte_alpha)
        edge_alpha_strength = edge_band * cleanup_strength
        keep = keep * (1.0 - edge_alpha_strength) + defringed_keep * edge_alpha_strength

    new_alpha = np.clip(original_alpha * keep, 0.0, 255.0)
    if cleanup_strength > 0:
        alpha_fraction = np.clip(matte_alpha, 1.0 / 255.0, 1.0)
        unmatted_rgb = (rgb - bg * (1.0 - alpha_fraction[:, :, None])) / alpha_fraction[
            :, :, None
        ]
        edge_strength = (1.0 - matte_alpha) * edge_band * cleanup_strength
        edge_strength = edge_strength[:, :, None] * (new_alpha[:, :, None] > 0)
        rgb = rgb * (1.0 - edge_strength) + unmatted_rgb * edge_strength

    edge_contract = _clamp(options.edge_contract, 0, 16)
    if edge_contract > 0:
        alpha_image = Image.fromarray(new_alpha.astype("uint8"), mode="L")
        alpha_image = alpha_image.filter(ImageFilter.MinFilter(edge_contract * 2 + 1))
        new_alpha = np.asarray(alpha_image).astype("float32")

    output = arr.copy()
    output[:, :, :3] = np.clip(rgb, 0.0, 255.0)
    output[:, :, 3] = new_alpha
    return Image.fromarray(output.astype("uint8"), mode="RGBA")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _selected_background_mask(
    hard_background,
    remove_scope: RemoveScopeMode,
    seed_points: tuple[tuple[int, int], ...],
):
    import numpy as np

    if remove_scope == "global":
        return hard_background
    if not hard_background.any():
        return np.zeros_like(hard_background, dtype=bool)

    try:
        import cv2
    except ImportError as exc:
        raise BackgroundRemoveUnavailable(
            "OpenCV is required for connected background removal. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    _label_count, labels = cv2.connectedComponents(
        hard_background.astype("uint8"),
        connectivity=8,
    )
    selected_labels: set[int] = set()
    height, width = hard_background.shape

    if remove_scope == "edge_connected":
        border_labels = np.concatenate(
            [
                labels[0, :],
                labels[height - 1, :],
                labels[:, 0],
                labels[:, width - 1],
            ]
        )
        selected_labels = {int(label) for label in border_labels if label != 0}
    elif remove_scope == "seed":
        for x, y in seed_points:
            if 0 <= x < width and 0 <= y < height:
                label = int(labels[y, x])
                if label != 0:
                    selected_labels.add(label)

    if not selected_labels:
        return np.zeros_like(hard_background, dtype=bool)
    return np.isin(labels, list(selected_labels))


def _soft_scope_mask(selected_background_mask, feather: int):
    if feather <= 0:
        return selected_background_mask

    radius = max(1, min(8, feather // 8 + 1))
    return selected_background_mask | (_edge_band_mask(selected_background_mask, radius) > 0)


def _edge_band_mask(background_mask, radius: int):
    import numpy as np

    mask_image = Image.fromarray((background_mask.astype("uint8") * 255), mode="L")
    dilated = mask_image.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    edge_band = np.asarray(dilated).astype("float32") / 255.0
    return edge_band * (1.0 - background_mask.astype("float32"))
