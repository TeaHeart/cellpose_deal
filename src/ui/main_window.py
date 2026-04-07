import os
import warnings
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsPolygonItem,
    QMainWindow,
    QProgressDialog,
)
from PySide6.QtCore import QModelIndex, Qt, Slot
from PySide6.QtGui import QPen, QPixmap
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

        self.ui.actionOpenFolder.triggered.connect(self.actionOpenFolder_triggered)
        self.ui.actionEvalCurrent.triggered.connect(self.actionEvalCurrent_triggered)
        self.ui.actionEvalAll.triggered.connect(self.actionEvalAll_triggered)

        self.setWindowTitle("Welcome")

        self.file_tree_viewer = FileTreeViewer(self, self.ui.treeView)
        self.file_tree_viewer.clicked.connect(self.treeView_clicked)

        self.image_viewer = ImageViewer(self, self.ui.graphicsView)

        self.table_viewer = TableViewer(self, self.ui.tableView)
        self.table_viewer.currentChanged.connect(self.tableView_currentChanged)

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
        self.ui.doubleSpinBox_px_size.setValue(value["px_size"])
        self.ui.doubleSpinBox_diam.setValue(value["diam"])
        self.ui.spinBox_niter.setValue(value["niter"])

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
    def treeView_clicked(self, current: QModelIndex):
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
        self.contours: dict[int, QGraphicsPolygonItem] = {}

        # 配置
        if os.path.isfile(yaml_file):
            with open(yaml_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)["cellpose"]

        # 遮罩
        if self.ui.actionLoadMask.isChecked():
            if os.path.isfile(npy_file):
                npy: np.ndarray = np.load(npy_file, allow_pickle=True)
                masks: np.ndarray = npy.item()["masks"]
                for label, contour in self.image_viewer.draw_contours(masks):
                    QApplication.processEvents()
                    self.contours[label] = contour

        # 表格
        if os.path.isfile(csv_file):
            df = pd.read_csv(csv_file)
            self.table_viewer.updateData(df)

    @Slot(QModelIndex, QModelIndex)
    def tableView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        green_pen = QPen(Qt.GlobalColor.green, 2)
        red_pen = QPen(Qt.GlobalColor.red, 2)

        if previous.isValid():
            particle_id = self.table_viewer.data(previous.row(), 0)
            item = self.contours[particle_id]
            item.setPen(green_pen)

        if current.isValid():
            particle_id = self.table_viewer.data(current.row(), 0)
            item = self.contours[particle_id]
            item.setPen(red_pen)
