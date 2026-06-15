from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
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
    zoom_changed = Signal(int)

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
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._is_panning = False
        self._last_pan_position = QPointF()

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
        self.fit_to_view()
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

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / 1.25)

    def fit_to_view(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.zoom_changed.emit(self.zoom_percent())
        self.update()

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        if self._source_size is None:
            return

        next_zoom = max(0.1, min(zoom, 8.0))
        if abs(next_zoom - self._zoom) < 0.001:
            return

        anchor = anchor or QPointF(self.width() / 2, self.height() / 2)
        source_anchor = self._view_to_source(anchor)
        self._zoom = next_zoom
        if source_anchor is not None:
            rect = self._image_rect()
            source_width, source_height = self._source_size
            desired_x = rect.left() + (source_anchor.x() / source_width) * rect.width()
            desired_y = rect.top() + (source_anchor.y() / source_height) * rect.height()
            self._pan += QPointF(anchor.x() - desired_x, anchor.y() - desired_y)

        self.zoom_changed.emit(self.zoom_percent())
        self.update()

    def zoom_percent(self) -> int:
        return int(round(self._zoom * 100))

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
        if event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            self._is_panning = True
            self._last_pan_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

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

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._is_panning:
            delta = event.position() - self._last_pan_position
            self._pan += delta
            self._last_pan_position = event.position()
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._is_panning and event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            self._is_panning = False
            self.setCursor(
                Qt.CursorShape.CrossCursor
                if self._pick_point_mode
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._source_size is None:
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return

        multiplier = 1.15 if delta > 0 else 1 / 1.15
        self.set_zoom(self._zoom * multiplier, event.position())
        event.accept()

    def _event_source_point(self, event) -> tuple[int, int] | None:
        if self._source_size is None:
            return None

        image_rect = self._image_rect()
        source_width, source_height = self._source_size
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            return None
        if not image_rect.contains(event.position().toPoint()):
            return None

        source_point = self._view_to_source(event.position())
        if source_point is None:
            return None

        return (int(source_point.x()), int(source_point.y()))

    def _view_to_source(self, point: QPointF) -> QPointF | None:
        if self._source_size is None:
            return None

        image_rect = self._image_rect()
        source_width, source_height = self._source_size
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            return None
        if not image_rect.contains(point.toPoint()):
            return None

        source_x = (point.x() - image_rect.left()) * source_width / image_rect.width()
        source_y = (point.y() - image_rect.top()) * source_height / image_rect.height()
        return QPointF(
            max(0.0, min(source_width - 1.0, source_x)),
            max(0.0, min(source_height - 1.0, source_y)),
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
        ) * self._zoom
        target_width = max(1, int(source_width * scale))
        target_height = max(1, int(source_height * scale))
        left = (
            content_rect.left()
            + (content_rect.width() - target_width) // 2
            + int(self._pan.x())
        )
        top = (
            content_rect.top()
            + (content_rect.height() - target_height) // 2
            + int(self._pan.y())
        )
        return QRect(left, top, target_width, target_height)

    def _draw_checkerboard(self, painter: QPainter, image_rect: QRect) -> None:
        tile = 16
        color_a = QColor("#2d323a")
        color_b = QColor("#242932")
        visible_rect = image_rect.intersected(self.rect())
        for y in range(visible_rect.top(), visible_rect.bottom() + 1, tile):
            for x in range(visible_rect.left(), visible_rect.right() + 1, tile):
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
