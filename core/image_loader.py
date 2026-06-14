from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def is_supported_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def iter_image_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in root.glob(pattern)
        if path.is_file() and is_supported_image(path)
    )


def normalize_image_paths(paths: Iterable[str | Path]) -> list[Path]:
    normalized: list[Path] = []
    seen: set[Path] = set()

    for raw_path in paths:
        path = Path(raw_path)
        candidates = iter_image_files(path) if path.is_dir() else [path]
        for candidate in candidates:
            if not candidate.is_file() or not is_supported_image(candidate):
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                normalized.append(resolved)
                seen.add(resolved)

    return normalized


def load_image(path: str | Path) -> Image.Image:
    image_path = Path(path)
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        return image.convert("RGBA")
