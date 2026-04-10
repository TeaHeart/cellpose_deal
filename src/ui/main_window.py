import os
import warnings
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMenu,
    QProgressDialog,
)
from PySide6.QtCore import QModelIndex, QPoint, Qt, Slot
from PySide6.QtGui import QPixmap
from cellpose import io
import numpy as np
import pandas as pd
import yaml
from ui.file_tree_viewer import FileTreeViewer
from ui.image_viewer import ImageViewer
from ui.inference_model import (
    InferenceConfig,
    InferenceModel,
    InferenceResult,
    InferenceWorker,
    masks_to_dataframe,
)
from ui.main_window_ui import Ui_MainWindow
from ui.table_viewer import TableViewer

warnings.filterwarnings("ignore", message="Sparse invariant checks")

IMAGE_EXTENSIONS = (".tif", ".tiff")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.menu_2.setEnabled(False)
        self.ui.actionEvalCurrent.setEnabled(False)
        self.ui.actionExportAll.setEnabled(False)
        self.ui.actionPreviousImage.setEnabled(False)
        self.ui.actionNextImage.setEnabled(False)

        self.ui.actionOpenFolder.triggered.connect(self.actionOpenFolder_triggered)
        self.ui.actionExportAll.triggered.connect(self.actionExportAll_triggered)
        self.ui.actionPreviousImage.triggered.connect(
            self.actionPreviousImage_triggered
        )
        self.ui.actionNextImage.triggered.connect(self.actionNextImage_triggered)
        self.ui.actionEvalCurrent.triggered.connect(self.actionEvalCurrent_triggered)
        self.ui.actionEvalAll.triggered.connect(self.actionEvalAll_triggered)

        self.setWindowTitle("Welcome")

        self.file_tree_viewer = FileTreeViewer(self, self.ui.treeView)
        self.file_tree_viewer.currentChanged.connect(self.treeView_currentChanged)
        self.ui.treeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(
            self.treeView_customContextMenuRequested
        )

        self.image_viewer = ImageViewer(self, self.ui.graphicsView)
        # 新增：连接轮廓点击信号
        self.image_viewer.contourClicked.connect(self._on_contour_clicked)
        # 新增：连接图片右键删除信号
        self.image_viewer.deleteToggled.connect(self._on_image_delete_toggled)

        self.table_viewer = TableViewer(self, self.ui.tableView)
        self.table_viewer.currentChanged.connect(self.tableView_currentChanged)
        # 新增：连接表格删除信号
        self.table_viewer.deleteToggled.connect(self._on_delete_toggled)

        self.model = InferenceModel()
        self.config = self.model.config

    def setWindowTitle(self, title: str):
        super().setWindowTitle(f"Cellpose Deal - {title}")

    @Slot()
    def actionOpenFolder_triggered(self):
        folder_path = QFileDialog.getExistingDirectory(self, "打开文件夹")

        if folder_path:
            self.file_tree_viewer.setRootPath(folder_path)
            self.ui.menu_2.setEnabled(True)
            self.ui.actionExportAll.setEnabled(True)
            self.ui.actionPreviousImage.setEnabled(True)
            self.ui.actionNextImage.setEnabled(True)

            self.setWindowTitle(folder_path)

    @property
    def config(self) -> InferenceConfig:
        return {
            "px_size": self.ui.doubleSpinBox_px_size.value(),
            "diam": self.ui.doubleSpinBox_diam.value(),
            "niter": self.ui.spinBox_niter.value(),
        }

    @config.setter
    def config(self, value: InferenceConfig):
        self.ui.doubleSpinBox_px_size.setValue(value["px_size"] or 18.5)
        self.ui.doubleSpinBox_diam.setValue(value["diam"] or 0)
        self.ui.spinBox_niter.setValue(value["niter"] or 0)

    @Slot()
    def actionExportAll_triggered(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存xlsx", "", "Excel文件 (*.xlsx)"
        )

        if file_path:
            if not file_path.endswith(".xlsx"):
                file_path += ".xlsx"

            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                root_path = self.file_tree_viewer.rootPath()

                for index in self.file_tree_viewer.listIndexes():
                    path = self.file_tree_viewer.filePath(index)
                    if path.lower().endswith(".csv"):
                        sheet = (
                            os.path.relpath(path, root_path)
                            .replace(os.path.sep, "_")
                            .replace(".csv", "")
                        )
                        df = pd.read_csv(path)

                        # 过滤 已删除 行和 已删除 列
                        if '已删除' in df.columns:
                            df = df[~df['已删除']].drop(columns=['已删除'])

                        df.to_excel(writer, sheet_name=sheet, index=False)

    @Slot()
    def actionPreviousImage_triggered(self):
        prev: QModelIndex = None
        selected = self.file_tree_viewer.currentIndex()

        for index in self.file_tree_viewer.listIndexes():
            if index == selected:
                if prev:
                    self.file_tree_viewer.setCurrentIndex(prev)
                break

            path = self.file_tree_viewer.filePath(index)
            if path.lower().endswith(IMAGE_EXTENSIONS):
                prev = index

    @Slot()
    def actionNextImage_triggered(self):
        selected = self.file_tree_viewer.currentIndex()
        found = False
        for index in self.file_tree_viewer.listIndexes():
            if not found:
                if index == selected:
                    found = True
            else:
                path = self.file_tree_viewer.filePath(index)
                if path.lower().endswith(IMAGE_EXTENSIONS):
                    self.file_tree_viewer.setCurrentIndex(index)
                    break

    @Slot()
    def actionEvalCurrent_triggered(self):
        file = self.file_tree_viewer.currentFile()

        if file.lower().endswith(IMAGE_EXTENSIONS):
            self.eval_images([file])

    @Slot()
    def actionEvalAll_triggered(self):
        files = self.file_tree_viewer.getFiles()
        files = [file for file in files if file.lower().endswith(IMAGE_EXTENSIONS)]
        self.eval_images(files)

    @Slot(QModelIndex)
    def treeView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        self.ui.actionEvalCurrent.setEnabled(False)

        if current.isValid():
            file_path = self.file_tree_viewer.filePath(current)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("current", file_path)

                    self.setEnabled(False)
                    self.load_files(file_path)
                    self.setEnabled(True)

                    self.ui.actionEvalCurrent.setEnabled(True)

    @Slot(QPoint)
    def treeView_customContextMenuRequested(self, position: QPoint):
        index = self.ui.treeView.indexAt(position)
        path = self.file_tree_viewer.filePath(index)
        basename = os.path.splitext(path)[0]
        yaml_file = f"{basename}.yaml"
        npy_file = f"{basename}.npy"
        csv_file = f"{basename}.csv"

        def npy2csv():
            npy: np.ndarray = np.load(npy_file, allow_pickle=True)
            masks: np.ndarray = npy.item()["masks"]

            with open(yaml_file, "r", encoding="utf-8") as f:
                config: InferenceConfig = yaml.safe_load(f)["cellpose"]

            df: pd.DataFrame = masks_to_dataframe(masks, config["px_size"])
            df.to_csv(csv_file, mode="w+", index=False, encoding="utf-8-sig")

        if index.isValid():
            menu = QMenu()
            lower_path = path.lower()

            if os.path.isfile(path):
                if lower_path.endswith("npy"):
                    menu.addAction("生成csv", npy2csv)

            if menu.actions():
                menu.exec_(self.ui.treeView.viewport().mapToGlobal(position))

    def eval_images(self, files: list[str]):
        total = len(files)
        if total == 0:
            return

        root_path = self.file_tree_viewer.rootPath()

        # 创建进度对话框
        progress = QProgressDialog("正在处理", "取消", 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)

        self.model.config = self.config
        worker = InferenceWorker(self.model, files)

        @Slot(int, int, str)
        def progress_updated(i: int, total: int, file: str):
            progress.setValue(i)
            progress.setWindowTitle(f"进度 {i}/{total}")
            if file:
                file = os.path.relpath(file, root_path)
                progress.setLabelText(f"正在处理: {file}")

        @Slot(InferenceResult)
        def file_completed(result: InferenceResult):
            file = result["file"]
            image = result["image"]
            masks = result["masks"]
            flows = result["flows"]
            df = result["df"]

            basename = os.path.splitext(file)[0]

            # 保存 {basename}_seg.npy 和 {basename}.csv
            io.masks_flows_to_seg(image, masks, flows, file)
            df.to_csv(f"{basename}.csv", mode="w+", index=False, encoding="utf-8-sig")

            with open(f"{basename}.yaml", "w+", encoding="utf-8") as f:
                yaml.safe_dump({"cellpose": self.model.config}, f)

            print(file, "完成")

        @Slot(list)
        def processing_finished(results: list[InferenceResult]):
            success_count = len([result for result in results if result["success"]])
            error_count = len(results) - success_count
            print(f"处理完成, 成功 {success_count} 个, 失败 {error_count} 个")

            if success_count > 0:
                for result in results:
                    if result["success"]:
                        self.load_files(result["file"])

        @Slot(str, Exception)
        def error_occurred(file: str, e: Exception):
            print(file, "处理失败", e)

        worker.progress_updated.connect(progress_updated)
        worker.file_completed.connect(file_completed)
        worker.all_finished.connect(processing_finished)
        worker.error_occurred.connect(error_occurred)

        progress.canceled.connect(worker.cancel)
        worker.start()
        progress.exec()

    def load_files(self, file_path: str):
        basename = os.path.splitext(file_path)[0]
        yaml_file = f"{basename}.yaml"
        npy_file = f"{basename}_seg.npy"
        csv_file = f"{basename}.csv"

        # 图片
        pixmap = QPixmap(file_path)
        self.image_viewer.set_pixmap(pixmap)

        self.table_viewer.updateData(pd.DataFrame())

        # 配置
        if os.path.isfile(yaml_file):
            with open(yaml_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)["cellpose"]

        # 遮罩
        if self.ui.actionLoadMask.isChecked():
            if os.path.isfile(npy_file):
                npy: np.ndarray = np.load(npy_file, allow_pickle=True)
                masks: np.ndarray = npy.item()["masks"]
                self.image_viewer.draw_contours(masks)

        # 表格
        if os.path.isfile(csv_file):
            df = pd.read_csv(csv_file)
            self.table_viewer.updateData(df)

            # 恢复删除状态到图片
            if '已删除' in df.columns:
                for row, deleted in enumerate(df['已删除']):
                    if deleted:
                        label = row + 1
                        self.image_viewer.set_deleted(label, True)

    @Slot(QModelIndex, QModelIndex)
    def tableView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        # 恢复之前选中轮廓的颜色（通过 ImageViewer 内部状态管理）
        if previous.isValid():
            particle_id = self.table_viewer.data(previous.row(), 0)
            self.image_viewer.set_deleted(particle_id, self.table_viewer._tableViewModel.is_deleted(previous.row()))

        # 设置新选中轮廓为红色
        if current.isValid():
            particle_id = self.table_viewer.data(current.row(), 0)
            self.image_viewer._select_contour(particle_id)

    @Slot(int)
    def _on_contour_clicked(self, label: int):
        """处理图片中细胞被点击"""
        # label 从 1 开始，row 从 0 开始
        row = label - 1
        self.table_viewer.selectRow(row)

    @Slot(int, bool)
    def _on_delete_toggled(self, row: int, deleted: bool):
        """处理表格行删除状态切换"""
        # row 从 0 开始，label 从 1 开始
        label = row + 1
        self.image_viewer.set_deleted(label, deleted)
        self._save_current_csv()

    @Slot(int, bool)
    def _on_image_delete_toggled(self, label: int, deleted: bool):
        """处理图片右键删除状态切换"""
        # label 从 1 开始，row 从 0 开始
        row = label - 1
        self.image_viewer.set_deleted(label, deleted)
        self.table_viewer._tableViewModel.set_deleted(row, deleted)
        self._save_current_csv()

    def _save_current_csv(self):
        """保存当前 CSV 文件"""
        current_file = self.file_tree_viewer.currentFile()
        if not current_file:
            return

        basename = os.path.splitext(current_file)[0]
        csv_file = f"{basename}.csv"

        try:
            self.table_viewer._tableViewModel.save_to_csv(csv_file)
        except Exception as e:
            print(f"保存失败: {e}")
