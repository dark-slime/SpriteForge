from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.sprite_slicer import SpriteSlice


def pil_image_to_qimage(image: Image.Image) -> QImage:
    rgba_image = image.convert("RGBA")
    width, height = rgba_image.size
    raw_data = rgba_image.tobytes("raw", "RGBA")
    return QImage(
        raw_data,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


class ImageCanvas(QWidget):
    slice_selected = Signal(int)
    source_point_clicked = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._image: QImage | None = None
        self._source_size: tuple[int, int] | None = None
        self._slices: list[SpriteSlice] = []
        self._selected_index: int | None = None
        self._pick_point_mode = False

    def set_image(self, image: Image.Image | None) -> None:
        if image is None:
            self._image = None
            self._source_size = None
            self._slices = []
            self._selected_index = None
        else:
            self._image = pil_image_to_qimage(image)
            self._source_size = image.size
            self._selected_index = None
        self.update()

    def set_slices(self, slices: list[SpriteSlice]) -> None:
        self._slices = slices
        self._selected_index = None
        self.update()

    def set_selected_slice(self, index: int | None) -> None:
        self._selected_index = index
        self.update()

    def set_pick_point_mode(self, enabled: bool) -> None:
        self._pick_point_mode = enabled
        self.setCursor(
            Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171a1f"))

        if self._image is None or self._source_size is None:
            self._draw_empty_state(painter)
            return

        image_rect = self._image_rect()
        self._draw_checkerboard(painter, image_rect)
        painter.drawImage(image_rect, self._image)
        self._draw_slices(painter, image_rect)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        source_point = self._event_source_point(event)
        if source_point is None:
            return

        source_x, source_y = source_point
        if self._pick_point_mode:
            self.source_point_clicked.emit(source_x, source_y)
            return

        candidates: list[tuple[int, int]] = []
        for index, sprite_slice in enumerate(self._slices):
            if (
                sprite_slice.x <= source_x <= sprite_slice.x + sprite_slice.width
                and sprite_slice.y <= source_y <= sprite_slice.y + sprite_slice.height
            ):
                candidates.append((sprite_slice.width * sprite_slice.height, index))

        if candidates:
            _area, index = min(candidates)
            self._selected_index = index
            self.slice_selected.emit(index)
            self.update()

    def _event_source_point(self, event) -> tuple[int, int] | None:
        if self._source_size is None:
            return None

        image_rect = self._image_rect()
        source_width, source_height = self._source_size
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            return None
        if not image_rect.contains(event.position().toPoint()):
            return None

        scale_x = source_width / image_rect.width()
        scale_y = source_height / image_rect.height()
        source_x = int((event.position().x() - image_rect.left()) * scale_x)
        source_y = int((event.position().y() - image_rect.top()) * scale_y)
        return (
            max(0, min(source_width - 1, source_x)),
            max(0, min(source_height - 1, source_y)),
        )

    def _draw_empty_state(self, painter: QPainter) -> None:
        painter.setPen(QColor("#aab2bf"))
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "拖入图片，或点击左侧导入按钮",
        )

    def _image_rect(self) -> QRect:
        if self._source_size is None:
            return QRect()

        source_width, source_height = self._source_size
        content_rect = self.rect().adjusted(18, 18, -18, -18)
        if source_width <= 0 or source_height <= 0:
            return content_rect

        scale = min(
            content_rect.width() / source_width,
            content_rect.height() / source_height,
        )
        target_width = max(1, int(source_width * scale))
        target_height = max(1, int(source_height * scale))
        left = content_rect.left() + (content_rect.width() - target_width) // 2
        top = content_rect.top() + (content_rect.height() - target_height) // 2
        return QRect(left, top, target_width, target_height)

    def _draw_checkerboard(self, painter: QPainter, image_rect: QRect) -> None:
        tile = 16
        color_a = QColor("#2d323a")
        color_b = QColor("#242932")
        for y in range(image_rect.top(), image_rect.bottom() + 1, tile):
            for x in range(image_rect.left(), image_rect.right() + 1, tile):
                offset = ((x - image_rect.left()) // tile) + (
                    (y - image_rect.top()) // tile
                )
                painter.fillRect(
                    QRect(x, y, tile, tile).intersected(image_rect),
                    color_a if offset % 2 == 0 else color_b,
                )

    def _draw_slices(self, painter: QPainter, image_rect: QRect) -> None:
        if self._source_size is None:
            return

        source_width, source_height = self._source_size
        scale_x = image_rect.width() / source_width
        scale_y = image_rect.height() / source_height

        label_font = QFont("Segoe UI", 9)
        label_font.setBold(True)
        painter.setFont(label_font)

        for index, sprite_slice in enumerate(self._slices):
            rect = QRectF(
                image_rect.left() + sprite_slice.x * scale_x,
                image_rect.top() + sprite_slice.y * scale_y,
                sprite_slice.width * scale_x,
                sprite_slice.height * scale_y,
            )
            selected = index == self._selected_index
            color = QColor("#58d68d") if selected else QColor("#45b7ff")
            painter.setPen(QPen(color, 2 if selected else 1.5))
            painter.drawRect(rect)
            if selected:
                self._draw_handles(painter, rect, color)

            label = f"{index + 1:02d}"
            label_rect = QRectF(rect.left(), rect.top(), 34, 20)
            painter.fillRect(label_rect, QColor(20, 24, 30, 210))
            painter.setPen(color)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_handles(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        handle_size = 7
        painter.setPen(QPen(color, 1))
        painter.setBrush(color)
        points = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
        ]
        for point in points:
            painter.drawRect(
                QRectF(
                    point.x() - handle_size / 2,
                    point.y() - handle_size / 2,
                    handle_size,
                    handle_size,
                )
            )
