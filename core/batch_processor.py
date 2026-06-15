from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.background_remove import (
    BackgroundRemover,
    SolidColorRemoveOptions,
    remove_solid_background,
)
from core.image_loader import load_image, normalize_image_paths
from core.sprite_slicer import SliceOptions, SpriteSlice, slice_image
from export.json_exporter import export_slices_json
from export.png_exporter import export_processed_image, export_sprites


@dataclass(slots=True)
class BatchItemResult:
    source_path: Path
    output_dir: Path
    slices: list[SpriteSlice] = field(default_factory=list)
    error: str | None = None


def process_batch(
    sources: list[str | Path],
    output_root: str | Path,
    options: SliceOptions,
    remove_background: bool = False,
    background_mode: str = "solid",
    solid_options: SolidColorRemoveOptions | None = None,
) -> list[BatchItemResult]:
    output_root_path = Path(output_root)
    image_paths = normalize_image_paths(sources)
    remover = BackgroundRemover() if remove_background and background_mode == "ai" else None
    solid_options = solid_options or SolidColorRemoveOptions()
    results: list[BatchItemResult] = []

    for image_path in image_paths:
        item_output = output_root_path / image_path.stem
        try:
            image = load_image(image_path)
            if remover is not None:
                image = remover.remove(image)
            elif remove_background:
                image = remove_solid_background(image, solid_options)

            slices = slice_image(image, options=options, base_name=image_path.stem)
            export_processed_image(image, item_output, image_path.stem)
            export_sprites(image, slices, item_output)
            export_slices_json(
                slices,
                item_output / f"{image_path.stem}.json",
                source_name=image_path.name,
                source_size=image.size,
            )
            results.append(
                BatchItemResult(
                    source_path=image_path,
                    output_dir=item_output,
                    slices=slices,
                )
            )
        except Exception as exc:  # Keep batch processing moving per file.
            results.append(
                BatchItemResult(
                    source_path=image_path,
                    output_dir=item_output,
                    error=str(exc),
                )
            )

    return results
