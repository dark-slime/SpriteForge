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
    slice_geometry_changed = Signal(int, int, int, int, int)
    zoom_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._image: QImage | None = None
        self._source_size: tuple[int, int] | None = None
        self._background_selection_overlay: QImage | None = None
        self._background_seed_points: list[tuple[int, int]] = []
        self._slices: list[SpriteSlice] = []
        self._selected_index: int | None = None
        self._pick_point_mode = False
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._is_panning = False
        self._last_pan_position = QPointF()
        self._drag_mode: str | None = None
        self._drag_handle: str | None = None
        self._drag_index: int | None = None
        self._drag_start_source = QPointF()
        self._drag_start_slice: SpriteSlice | None = None

    def set_image(self, image: Image.Image | None) -> None:
        if image is None:
            self._image = None
            self._source_size = None
            self._background_selection_overlay = None
            self._background_seed_points = []
            self._slices = []
            self._selected_index = None
        else:
            self._image = pil_image_to_qimage(image)
            self._source_size = image.size
            self._selected_index = None
        self.fit_to_view()
        self.update()

    def set_background_selection_mask(self, mask: Image.Image | None) -> None:
        if mask is None:
            self._background_selection_overlay = None
            self.update()
            return

        alpha = mask.convert("L").point(lambda value: 82 if value else 0)
        overlay = Image.new("RGBA", mask.size, (88, 214, 141, 0))
        overlay.putalpha(alpha)
        self._background_selection_overlay = pil_image_to_qimage(overlay)
        self.update()

    def set_background_seed_points(self, points: list[tuple[int, int]]) -> None:
        self._background_seed_points = list(points)
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
        self._draw_background_selection(painter, image_rect)
        self._draw_background_seed_points(painter, image_rect)
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

        if event.button() == Qt.MouseButton.LeftButton:
            handle_hit = self._hit_handle(event.position())
            if handle_hit is not None:
                index, handle = handle_hit
                self._selected_index = index
                self.slice_selected.emit(index)
                self._start_slice_drag(index, "resize", QPointF(source_x, source_y), handle)
                event.accept()
                return

            if self._selected_index is not None:
                selected = self._slices[self._selected_index]
                if _slice_contains(selected, source_x, source_y):
                    self._start_slice_drag(
                        self._selected_index,
                        "move",
                        QPointF(source_x, source_y),
                    )
                    event.accept()
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
        if self._drag_mode is not None:
            source_point = self._event_source_point(event)
            if source_point is not None:
                self._update_slice_drag(QPointF(source_point[0], source_point[1]))
            event.accept()
            return

        if self._is_panning:
            delta = event.position() - self._last_pan_position
            self._pan += delta
            self._last_pan_position = event.position()
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_mode is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_mode = None
            self._drag_handle = None
            self._drag_index = None
            self._drag_start_slice = None
            self.setCursor(
                Qt.CursorShape.CrossCursor
                if self._pick_point_mode
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            return

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

    def _start_slice_drag(
        self,
        index: int,
        mode: str,
        source_point: QPointF,
        handle: str | None = None,
    ) -> None:
        self._drag_index = index
        self._drag_mode = mode
        self._drag_handle = handle
        self._drag_start_source = source_point
        self._drag_start_slice = self._slices[index]
        self.setCursor(
            Qt.CursorShape.SizeAllCursor
            if mode == "move"
            else self._cursor_for_handle(handle)
        )

    def _update_slice_drag(self, source_point: QPointF) -> None:
        if (
            self._drag_index is None
            or self._drag_start_slice is None
            or self._source_size is None
        ):
            return

        delta_x = int(round(source_point.x() - self._drag_start_source.x()))
        delta_y = int(round(source_point.y() - self._drag_start_source.y()))
        original = self._drag_start_slice

        if self._drag_mode == "move":
            x = original.x + delta_x
            y = original.y + delta_y
            width = original.width
            height = original.height
        else:
            left = original.x
            top = original.y
            right = original.x + original.width
            bottom = original.y + original.height
            handle = self._drag_handle or "br"
            if "l" in handle:
                left += delta_x
            if "r" in handle:
                right += delta_x
            if "t" in handle:
                top += delta_y
            if "b" in handle:
                bottom += delta_y

            if right < left:
                left, right = right, left
            if bottom < top:
                top, bottom = bottom, top
            x = left
            y = top
            width = max(1, right - left)
            height = max(1, bottom - top)

        self.slice_geometry_changed.emit(self._drag_index, x, y, width, height)

    def _hit_handle(self, point: QPointF) -> tuple[int, str] | None:
        if self._source_size is None:
            return None

        image_rect = self._image_rect()
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            return None

        for index, sprite_slice in reversed(list(enumerate(self._slices))):
            handles = self._slice_handle_rects(sprite_slice, image_rect)
            for handle_name, handle_rect in handles.items():
                if handle_rect.contains(point):
                    return index, handle_name
        return None

    def _slice_handle_rects(
        self,
        sprite_slice: SpriteSlice,
        image_rect: QRect,
    ) -> dict[str, QRectF]:
        if self._source_size is None:
            return {}

        source_width, source_height = self._source_size
        scale_x = image_rect.width() / source_width
        scale_y = image_rect.height() / source_height
        rect = QRectF(
            image_rect.left() + sprite_slice.x * scale_x,
            image_rect.top() + sprite_slice.y * scale_y,
            sprite_slice.width * scale_x,
            sprite_slice.height * scale_y,
        )
        handle_size = 12
        return {
            "tl": _centered_rect(rect.topLeft(), handle_size),
            "tr": _centered_rect(rect.topRight(), handle_size),
            "bl": _centered_rect(rect.bottomLeft(), handle_size),
            "br": _centered_rect(rect.bottomRight(), handle_size),
            "t": _edge_rect(rect, "t", handle_size),
            "b": _edge_rect(rect, "b", handle_size),
            "l": _edge_rect(rect, "l", handle_size),
            "r": _edge_rect(rect, "r", handle_size),
        }

    def _cursor_for_handle(self, handle: str | None) -> Qt.CursorShape:
        if handle in ("tl", "br"):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in ("tr", "bl"):
            return Qt.CursorShape.SizeBDiagCursor
        if handle in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        if handle in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

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
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, 2 if selected else 1.5))
            painter.drawRect(rect)
            if selected:
                self._draw_handles(painter, rect, color)

            label = f"{index + 1:02d}"
            label_rect = QRectF(rect.left(), rect.top(), 34, 20)
            painter.fillRect(label_rect, QColor(20, 24, 30, 210))
            painter.setPen(color)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_background_selection(self, painter: QPainter, image_rect: QRect) -> None:
        if self._background_selection_overlay is None:
            return

        painter.save()
        painter.drawImage(image_rect, self._background_selection_overlay)
        painter.restore()

    def _draw_background_seed_points(self, painter: QPainter, image_rect: QRect) -> None:
        if self._source_size is None or not self._background_seed_points:
            return

        source_width, source_height = self._source_size
        scale_x = image_rect.width() / source_width
        scale_y = image_rect.height() / source_height

        painter.save()
        point_color = QColor("#58d68d")
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        for index, (source_x, source_y) in enumerate(self._background_seed_points, start=1):
            view_x = image_rect.left() + source_x * scale_x
            view_y = image_rect.top() + source_y * scale_y
            marker_rect = QRectF(view_x - 7, view_y - 7, 14, 14)
            painter.setPen(QPen(QColor("#123526"), 2))
            painter.setBrush(point_color)
            painter.drawEllipse(marker_rect)

            label = str(index)
            label_rect = QRectF(view_x + 8, view_y - 16, 22, 18)
            painter.fillRect(label_rect, QColor(20, 24, 30, 220))
            painter.setPen(point_color)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

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
        painter.setBrush(Qt.BrushStyle.NoBrush)


def _slice_contains(sprite_slice: SpriteSlice, x: int, y: int) -> bool:
    return (
        sprite_slice.x <= x <= sprite_slice.x + sprite_slice.width
        and sprite_slice.y <= y <= sprite_slice.y + sprite_slice.height
    )


def _centered_rect(point: QPointF, size: int) -> QRectF:
    return QRectF(point.x() - size / 2, point.y() - size / 2, size, size)


def _edge_rect(rect: QRectF, edge: str, size: int) -> QRectF:
    if edge == "t":
        return QRectF(
            rect.left() + size,
            rect.top() - size / 2,
            max(1, rect.width() - size * 2),
            size,
        )
    if edge == "b":
        return QRectF(
            rect.left() + size,
            rect.bottom() - size / 2,
            max(1, rect.width() - size * 2),
            size,
        )
    if edge == "l":
        return QRectF(
            rect.left() - size / 2,
            rect.top() + size,
            size,
            max(1, rect.height() - size * 2),
        )
    return QRectF(
        rect.right() - size / 2,
        rect.top() + size,
        size,
        max(1, rect.height() - size * 2),
    )
