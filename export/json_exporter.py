from __future__ import annotations

import json
from pathlib import Path

from core.sprite_slicer import SpriteSlice


def export_slices_json(
    slices: list[SpriteSlice],
    output_path: str | Path,
    source_name: str | None = None,
    source_size: tuple[int, int] | None = None,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {
        "sprites": [sprite_slice.to_json() for sprite_slice in slices],
    }
    if source_name:
        payload["source"] = source_name
    if source_size:
        payload["image_width"] = source_size[0]
        payload["image_height"] = source_size[1]

    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
