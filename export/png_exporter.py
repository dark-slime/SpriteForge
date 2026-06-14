from __future__ import annotations

from pathlib import Path

from PIL import Image

from core.sprite_slicer import SpriteSlice


def export_processed_image(
    image: Image.Image,
    output_dir: str | Path,
    source_stem: str,
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    target = output_path / f"{source_stem}_removed.png"
    image.convert("RGBA").save(target, format="PNG")
    return target


def export_sprites(
    image: Image.Image,
    slices: list[SpriteSlice],
    output_dir: str | Path,
) -> list[Path]:
    sprites_dir = Path(output_dir)
    sprites_dir.mkdir(parents=True, exist_ok=True)

    rgba_image = image.convert("RGBA")
    exported: list[Path] = []
    for sprite_slice in slices:
        target = sprites_dir / f"{sprite_slice.name}.png"
        rgba_image.crop(sprite_slice.crop_box).save(target, format="PNG")
        exported.append(target)

    return exported
