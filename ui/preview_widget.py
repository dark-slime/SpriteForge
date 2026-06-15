from __future__ import annotations

from PIL import Image, ImageDraw
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem

from core.sprite_slicer import SpriteSlice
from ui.image_view import pil_image_to_qimage


class PreviewWidget(QListWidget):
    slice_selected = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._icon_size = 112
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self.setGridSize(QSize(142, 150))
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumHeight(172)
        self.setStyleSheet(
            """
            QListWidget {
                background: #151920;
                border: 1px solid #2f3642;
                color: #d8dee9;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #24435f;
                color: #ffffff;
            }
            """
        )
        self.itemClicked.connect(self._emit_slice_selected)

    def set_slices(self, image: Image.Image | None, slices: list[SpriteSlice]) -> None:
        self.clear()
        if image is None:
            return

        rgba_image = image.convert("RGBA")
        for index, sprite_slice in enumerate(slices):
            thumbnail = rgba_image.crop(sprite_slice.crop_box)
            pixmap = self._thumbnail_pixmap(thumbnail)

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

    def _thumbnail_pixmap(self, image: Image.Image) -> QPixmap:
        size = self._icon_size
        thumbnail = image.convert("RGBA")
        thumbnail.thumbnail((size - 14, size - 14), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 255))
        draw = ImageDraw.Draw(canvas)
        tile = 14
        for y in range(0, size, tile):
            for x in range(0, size, tile):
                color = (47, 53, 63, 255) if (x // tile + y // tile) % 2 == 0 else (
                    38,
                    44,
                    53,
                    255,
                )
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=color)

        offset = ((size - thumbnail.width) // 2, (size - thumbnail.height) // 2)
        canvas.alpha_composite(thumbnail, offset)
        return QPixmap.fromImage(pil_image_to_qimage(canvas))
