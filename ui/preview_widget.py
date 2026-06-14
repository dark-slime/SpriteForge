from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from core.sprite_slicer import SpriteSlice
from ui.image_view import pil_image_to_qimage


class PreviewWidget(QListWidget):
    slice_selected = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(QSize(96, 96))
        self.setGridSize(QSize(126, 132))
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.itemClicked.connect(self._emit_slice_selected)

    def set_slices(self, image: Image.Image | None, slices: list[SpriteSlice]) -> None:
        self.clear()
        if image is None:
            return

        rgba_image = image.convert("RGBA")
        for index, sprite_slice in enumerate(slices):
            thumbnail = rgba_image.crop(sprite_slice.crop_box)
            thumbnail.thumbnail((96, 96), Image.Resampling.LANCZOS)
            pixmap = QPixmap.fromImage(pil_image_to_qimage(thumbnail))

            item = QListWidgetItem(QIcon(pixmap), sprite_slice.name)
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setToolTip(
                f"{sprite_slice.name}\n"
                f"x={sprite_slice.x}, y={sprite_slice.y}, "
                f"w={sprite_slice.width}, h={sprite_slice.height}"
            )
            self.addItem(item)

    def select_slice(self, index: int | None) -> None:
        self.clearSelection()
        if index is None:
            return
        item = self.item(index)
        if item is not None:
            item.setSelected(True)
            self.scrollToItem(item)

    def _emit_slice_selected(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int):
            self.slice_selected.emit(index)
