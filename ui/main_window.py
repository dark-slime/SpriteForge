from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QSpinBox,
    QSplitter,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.background_remove import (
    BackgroundRemoveUnavailable,
    BackgroundRemover,
    SolidColorRemoveOptions,
    remove_solid_background,
    sample_background_color,
)
from core.batch_processor import process_batch
from core.image_loader import is_supported_image, load_image, normalize_image_paths
from core.sprite_slicer import (
    SliceOptions,
    SpriteSlice,
    SpriteSlicerDependencyError,
    slice_image,
)
from export.json_exporter import export_slices_json
from export.png_exporter import export_processed_image, export_sprites
from ui.image_view import ImageCanvas
from ui.preview_widget import PreviewWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SpriteForge")
        self.resize(1280, 820)
        self.setAcceptDrops(True)

        self.image_paths: list[Path] = []
        self.current_path: Path | None = None
        self.current_image: Image.Image | None = None
        self.current_slices: list[SpriteSlice] = []
        self.background_remover = BackgroundRemover()

        self._create_actions()
        self._create_menu()
        self._create_toolbar()
        self._create_widgets()
        self.statusBar().showMessage("Ready")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._mime_has_images(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        self._add_image_paths(paths)
        event.acceptProposedAction()

    def _create_actions(self) -> None:
        style = self.style()
        self.import_images_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            "导入图片",
            self,
        )
        self.import_images_action.triggered.connect(self._select_images)

        self.import_folder_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
            "导入文件夹",
            self,
        )
        self.import_folder_action.triggered.connect(self._select_folder)

        self.remove_background_action = QAction("去背景", self)
        self.remove_background_action.triggered.connect(self._remove_background)

        self.slice_action = QAction("自动切图", self)
        self.slice_action.triggered.connect(self._slice_current_image)

        self.export_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            "导出结果",
            self,
        )
        self.export_action.triggered.connect(self._export_current)

        self.batch_action = QAction("批量处理", self)
        self.batch_action.triggered.connect(self._batch_process)

        self.quit_action = QAction("退出", self)
        self.quit_action.triggered.connect(self.close)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.import_images_action)
        file_menu.addAction(self.import_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        process_menu = self.menuBar().addMenu("处理")
        process_menu.addAction(self.remove_background_action)
        process_menu.addAction(self.slice_action)
        process_menu.addAction(self.batch_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(self.import_images_action)
        toolbar.addAction(self.import_folder_action)
        toolbar.addSeparator()
        toolbar.addAction(self.remove_background_action)
        toolbar.addAction(self.slice_action)
        toolbar.addSeparator()
        toolbar.addAction(self.export_action)
        toolbar.addAction(self.batch_action)
        self.addToolBar(toolbar)

    def _create_widgets(self) -> None:
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(260)
        self.file_list.currentItemChanged.connect(self._on_file_selected)

        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(0, 255)
        self.alpha_spin.setValue(10)

        self.min_area_spin = QSpinBox()
        self.min_area_spin.setRange(0, 10_000_000)
        self.min_area_spin.setValue(64)

        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 512)
        self.padding_spin.setValue(4)

        self.bg_mode_combo = QComboBox()
        self.bg_mode_combo.addItem("纯色快速", "solid")
        self.bg_mode_combo.addItem("AI rembg", "ai")

        self.bg_sample_combo = QComboBox()
        self.bg_sample_combo.addItem("四角自动", "corners")
        self.bg_sample_combo.addItem("左上角", "top_left")
        self.bg_sample_combo.addItem("手动 RGB", "manual")

        self.bg_r_spin = QSpinBox()
        self.bg_g_spin = QSpinBox()
        self.bg_b_spin = QSpinBox()
        for spin in (self.bg_r_spin, self.bg_g_spin, self.bg_b_spin):
            spin.setRange(0, 255)
            spin.setValue(255)

        self.bg_tolerance_spin = QSpinBox()
        self.bg_tolerance_spin.setRange(0, 255)
        self.bg_tolerance_spin.setValue(28)

        self.bg_feather_spin = QSpinBox()
        self.bg_feather_spin.setRange(0, 255)
        self.bg_feather_spin.setValue(10)

        self.bg_spill_spin = QSpinBox()
        self.bg_spill_spin.setRange(0, 100)
        self.bg_spill_spin.setValue(60)

        self.merge_check = QCheckBox("合并邻近区域")
        self.batch_remove_check = QCheckBox("批量时去背景")

        self.naming_combo = QComboBox()
        self.naming_combo.addItem("sprite_001", "sprite")
        self.naming_combo.addItem("文件名_001", "filename")

        left_panel = self._build_left_panel()

        self.canvas = ImageCanvas()
        self.canvas.slice_selected.connect(self._select_slice)

        self.preview = PreviewWidget()
        self.preview.setMinimumHeight(170)
        self.preview.slice_selected.connect(self._select_slice)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.canvas)
        right_splitter.addWidget(self.preview)
        right_splitter.setStretchFactor(0, 4)
        right_splitter.setStretchFactor(1, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(360)
        layout = QVBoxLayout(panel)

        import_button = QPushButton("导入图片")
        import_button.setIcon(self.import_images_action.icon())
        import_button.clicked.connect(self._select_images)

        folder_button = QPushButton("导入文件夹")
        folder_button.setIcon(self.import_folder_action.icon())
        folder_button.clicked.connect(self._select_folder)

        remove_button = QPushButton("去背景")
        remove_button.clicked.connect(self._remove_background)

        slice_button = QPushButton("自动切图")
        slice_button.clicked.connect(self._slice_current_image)

        export_button = QPushButton("导出结果")
        export_button.setIcon(self.export_action.icon())
        export_button.clicked.connect(self._export_current)

        batch_button = QPushButton("批量处理")
        batch_button.clicked.connect(self._batch_process)

        file_group = QGroupBox("图片")
        file_layout = QVBoxLayout(file_group)
        file_layout.addWidget(import_button)
        file_layout.addWidget(folder_button)
        file_layout.addWidget(self.file_list)

        process_group = QGroupBox("操作")
        process_layout = QVBoxLayout(process_group)
        process_layout.addWidget(remove_button)
        process_layout.addWidget(slice_button)
        process_layout.addWidget(export_button)
        process_layout.addWidget(batch_button)

        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(QLabel("R"))
        color_layout.addWidget(self.bg_r_spin)
        color_layout.addWidget(QLabel("G"))
        color_layout.addWidget(self.bg_g_spin)
        color_layout.addWidget(QLabel("B"))
        color_layout.addWidget(self.bg_b_spin)

        sample_button = QPushButton("取左上角")
        sample_button.clicked.connect(self._sample_top_left_color)

        background_group = QGroupBox("去背景参数")
        background_layout = QFormLayout(background_group)
        background_layout.addRow("模式", self.bg_mode_combo)
        background_layout.addRow("背景采样", self.bg_sample_combo)
        background_layout.addRow("手动颜色", color_widget)
        background_layout.addRow("容差", self.bg_tolerance_spin)
        background_layout.addRow("羽化", self.bg_feather_spin)
        background_layout.addRow("去白边", self.bg_spill_spin)
        background_layout.addRow(sample_button)
        background_layout.addRow(self.batch_remove_check)

        params_group = QGroupBox("切图参数")
        params_layout = QFormLayout(params_group)
        params_layout.addRow("Alpha 阈值", self.alpha_spin)
        params_layout.addRow("最小面积", self.min_area_spin)
        params_layout.addRow("Padding", self.padding_spin)
        params_layout.addRow("导出命名", self.naming_combo)
        params_layout.addRow(self.merge_check)

        layout.addWidget(file_group)
        layout.addWidget(process_group)
        layout.addWidget(background_group)
        layout.addWidget(params_group)
        layout.addStretch(1)

        count_label = QLabel("0 images")
        count_label.setObjectName("countLabel")
        self.count_label = count_label
        layout.addWidget(count_label)

        return panel

    def _select_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "导入图片",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        self._add_image_paths([Path(path) for path in paths])

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "导入文件夹", str(Path.home()))
        if folder:
            self._add_image_paths([Path(folder)])

    def _add_image_paths(self, raw_paths: list[Path]) -> None:
        new_paths = normalize_image_paths(raw_paths)
        if not new_paths:
            self.statusBar().showMessage("No supported images found", 4000)
            return

        known = {path.resolve() for path in self.image_paths}
        first_new_row: int | None = None
        for path in new_paths:
            resolved = path.resolve()
            if resolved in known:
                continue
            self.image_paths.append(resolved)
            item = QListWidgetItem(resolved.name)
            item.setToolTip(str(resolved))
            item.setData(Qt.ItemDataRole.UserRole, str(resolved))
            self.file_list.addItem(item)
            known.add(resolved)
            if first_new_row is None:
                first_new_row = self.file_list.count() - 1

        self._refresh_count()
        if first_new_row is not None and self.current_image is None:
            self.file_list.setCurrentRow(first_new_row)
        self.statusBar().showMessage(f"Imported {len(new_paths)} image(s)", 4000)

    def _on_file_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        path_value = current.data(Qt.ItemDataRole.UserRole)
        if path_value:
            self._load_current_image(Path(path_value))

    def _load_current_image(self, path: Path) -> None:
        try:
            image = load_image(path)
        except Exception as exc:
            self._show_error("导入失败", str(exc))
            return

        self.current_path = path
        self.current_image = image
        self.current_slices = []
        self.canvas.set_image(image)
        self.canvas.set_slices([])
        self.preview.set_slices(image, [])
        self.statusBar().showMessage(f"Loaded {path.name}")

    def _remove_background(self) -> None:
        if self.current_image is None:
            self._show_warning("请先导入图片")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage("正在去背景...")
        try:
            if self.bg_mode_combo.currentData() == "ai":
                self.current_image = self.background_remover.remove(self.current_image)
            else:
                self.current_image = remove_solid_background(
                    self.current_image,
                    self._solid_background_options(),
                )
        except BackgroundRemoveUnavailable as exc:
            self._show_error("去背景不可用", str(exc))
            return
        except Exception as exc:
            self._show_error("去背景失败", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.current_slices = []
        self.canvas.set_image(self.current_image)
        self.canvas.set_slices([])
        self.preview.set_slices(self.current_image, [])
        self.statusBar().showMessage("去背景完成", 5000)

    def _slice_current_image(self) -> None:
        if self.current_image is None:
            self._show_warning("请先导入图片")
            return

        try:
            self.current_slices = slice_image(
                self.current_image,
                options=self._slice_options(),
                base_name=self.current_path.stem if self.current_path else None,
            )
        except SpriteSlicerDependencyError as exc:
            self._show_error("OpenCV 不可用", str(exc))
            return
        except Exception as exc:
            self._show_error("自动切图失败", str(exc))
            return

        self.canvas.set_slices(self.current_slices)
        self.preview.set_slices(self.current_image, self.current_slices)
        self.statusBar().showMessage(f"Detected {len(self.current_slices)} sprite(s)")

    def _export_current(self) -> None:
        if self.current_image is None:
            self._show_warning("请先导入图片")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "导出结果",
            str(Path.cwd() / "output"),
        )
        if not output_dir:
            return

        source_stem = self.current_path.stem if self.current_path else "source"
        output_path = Path(output_dir)
        try:
            export_processed_image(self.current_image, output_path, source_stem)
            export_sprites(self.current_image, self.current_slices, output_path / "sprites")
            export_slices_json(
                self.current_slices,
                output_path / f"{source_stem}.json",
                source_name=self.current_path.name if self.current_path else None,
                source_size=self.current_image.size,
            )
        except Exception as exc:
            self._show_error("导出失败", str(exc))
            return

        self.statusBar().showMessage(f"Exported to {output_path}", 7000)

    def _batch_process(self) -> None:
        if not self.image_paths:
            self._show_warning("请先导入图片或文件夹")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "批量输出目录",
            str(Path.cwd() / "output"),
        )
        if not output_dir:
            return

        progress = QProgressDialog("批量处理中...", "取消", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()

        try:
            results = process_batch(
                self.image_paths,
                output_dir,
                self._slice_options(),
                remove_background=self.batch_remove_check.isChecked(),
                background_mode=self.bg_mode_combo.currentData(),
                solid_options=self._solid_background_options(),
            )
        finally:
            progress.close()

        failed = [result for result in results if result.error]
        succeeded = len(results) - len(failed)
        if failed:
            details = "\n".join(
                f"{result.source_path.name}: {result.error}" for result in failed[:8]
            )
            QMessageBox.warning(
                self,
                "批量处理完成",
                f"成功 {succeeded} 个，失败 {len(failed)} 个。\n\n{details}",
            )
        else:
            QMessageBox.information(self, "批量处理完成", f"成功处理 {succeeded} 个文件。")

        self.statusBar().showMessage(f"Batch exported to {output_dir}", 7000)

    def _slice_options(self) -> SliceOptions:
        return SliceOptions(
            alpha_threshold=self.alpha_spin.value(),
            min_area=self.min_area_spin.value(),
            padding=self.padding_spin.value(),
            merge_nearby=self.merge_check.isChecked(),
            naming_mode=self.naming_combo.currentData(),
        )

    def _solid_background_options(self) -> SolidColorRemoveOptions:
        return SolidColorRemoveOptions(
            background_color=(
                self.bg_r_spin.value(),
                self.bg_g_spin.value(),
                self.bg_b_spin.value(),
            ),
            sample_mode=self.bg_sample_combo.currentData(),
            tolerance=self.bg_tolerance_spin.value(),
            feather=self.bg_feather_spin.value(),
            spill_cleanup=self.bg_spill_spin.value(),
        )

    def _sample_top_left_color(self) -> None:
        if self.current_image is None:
            self._show_warning("请先导入图片")
            return

        red, green, blue = sample_background_color(self.current_image, "top_left")
        self.bg_r_spin.setValue(red)
        self.bg_g_spin.setValue(green)
        self.bg_b_spin.setValue(blue)
        manual_index = self.bg_sample_combo.findData("manual")
        if manual_index >= 0:
            self.bg_sample_combo.setCurrentIndex(manual_index)
        self.statusBar().showMessage(
            f"已取色 RGB({red}, {green}, {blue})",
            4000,
        )

    def _select_slice(self, index: int) -> None:
        self.canvas.set_selected_slice(index)
        self.preview.select_slice(index)

    def _refresh_count(self) -> None:
        self.count_label.setText(f"{len(self.image_paths)} images")

    def _mime_has_images(self, mime_data) -> bool:
        if not mime_data.hasUrls():
            return False
        for url in mime_data.urls():
            path = Path(url.toLocalFile())
            if path.is_dir() or (path.is_file() and is_supported_image(path)):
                return True
        return False

    def _show_warning(self, message: str) -> None:
        QMessageBox.warning(self, "SpriteForge", message)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
