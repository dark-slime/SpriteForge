from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from PIL import Image, ImageFilter


ColorSampleMode = Literal["corners", "top_left", "manual"]


class BackgroundRemoveUnavailable(RuntimeError):
    """Raised when rembg is not installed or cannot run."""


@dataclass(slots=True)
class SolidColorRemoveOptions:
    background_color: tuple[int, int, int] | None = None
    sample_mode: ColorSampleMode = "corners"
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

    channel_ranges = np.maximum(bg, 255.0 - bg)
    channel_ranges = np.maximum(channel_ranges, 1.0)
    matte_alpha = np.max(color_delta / channel_ranges, axis=2)
    tolerance_fraction = tolerance / 255.0
    matte_alpha = np.clip(
        (matte_alpha - tolerance_fraction) / max(1.0 - tolerance_fraction, 1.0 / 255.0),
        0.0,
        1.0,
    )

    if cleanup_strength > 0:
        edge_band = _edge_band_mask(keep <= 0.01, radius=max(1, min(4, feather // 16 + 1)))
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


class BackgroundRemover:
    def __init__(self, model_name: str = "u2net") -> None:
        self.model_name = model_name
        self._session = None

    def is_available(self) -> bool:
        try:
            import rembg  # noqa: F401
        except ImportError:
            return False
        return True

    def remove(self, image: Image.Image) -> Image.Image:
        try:
            from rembg import new_session, remove
        except ImportError as exc:
            raise BackgroundRemoveUnavailable(
                "rembg is not installed. Install dependencies with: "
                "pip install -r requirements.txt"
            ) from exc

        if self._session is None:
            self._session = new_session(self.model_name)

        input_buffer = BytesIO()
        image.convert("RGBA").save(input_buffer, format="PNG")
        output_bytes = remove(input_buffer.getvalue(), session=self._session)

        with Image.open(BytesIO(output_bytes)) as result:
            return result.convert("RGBA")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _edge_band_mask(background_mask, radius: int):
    import numpy as np

    mask_image = Image.fromarray((background_mask.astype("uint8") * 255), mode="L")
    dilated = mask_image.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    edge_band = np.asarray(dilated).astype("float32") / 255.0
    return edge_band * (1.0 - background_mask.astype("float32"))
