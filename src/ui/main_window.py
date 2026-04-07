import os
import warnings
from PySide6.QtWidgets import QFileDialog, QMainWindow, QProgressDialog
from PySide6.QtCore import QModelIndex, Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from cellpose import io
import cv2
import numpy as np
import pandas as pd
from ui.file_tree_viewer import FileTreeViewer
from ui.image_viewer import ImageViewer
from ui.inference_model import InferenceModel, InferenceResult, InferenceWorker
from ui.main_window_ui import Ui_MainWindow
from ui.table_viewer import TableViewer

warnings.filterwarnings("ignore", message="Sparse invariant checks")

IMAGE_EXTENSIONS = (".tif", ".tiff")


def draw_masks_on_image(image: np.ndarray, masks: np.ndarray, show_outlines=True):
    """
    在图像上绘制mask轮廓
    """
    # 确保图像是RGB格式
    if len(image.shape) == 2:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        image_rgb = image.copy()

    # 为每个颗粒绘制轮廓
    for label in range(1, masks.max() + 1):
        # 创建单个mask
        mask = (masks == label).astype(np.uint8)

        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 绘制轮廓
        cv2.drawContours(image_rgb, contours, -1, (0, 255, 0), 2)

        # 可选：在颗粒中心添加标签
        if show_outlines:
            # 计算质心
            moments = cv2.moments(mask)
            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                cv2.putText(
                    image_rgb,
                    str(label),
                    (cx, cy),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    2,
                )

    return image_rgb


def numpy_to_qpixmap(np_image: np.ndarray):
    """
    将numpy数组转换为QPixmap
    """
    if len(np_image.shape) == 2:
        # 灰度图
        height, width = np_image.shape
        bytes_per_line = width
        qimage = QImage(
            np_image.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_Grayscale8,
        )
    elif len(np_image.shape) == 3 and np_image.shape[2] == 3:
        # RGB图
        height, width, channel = np_image.shape
        bytes_per_line = 3 * width
        qimage = QImage(
            np_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
        )
    elif len(np_image.shape) == 3 and np_image.shape[2] == 4:
        # RGBA图
        height, width, channel = np_image.shape
        bytes_per_line = 4 * width
        qimage = QImage(
            np_image.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888
        )
    else:
        raise ValueError("Unsupported image format")

    return QPixmap.fromImage(qimage)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.actionOpenFolder.triggered.connect(self.actionOpenFolder_triggered)
        self.ui.actionModelConfig.triggered.connect(self.actionModelConfig_triggered)
        self.ui.actionEvalCurrent.triggered.connect(self.actionEvalCurrent_triggered)
        self.ui.actionEvalAll.triggered.connect(self.actionEvalAll_triggered)

        self.setWindowTitle("Welcome")

        self.file_tree_viewer = FileTreeViewer(self, self.ui.treeView)
        self.file_tree_viewer.currentChanged.connect(self.treeView_currentChanged)

        self.image_viewer = ImageViewer(self, self.ui.graphicsView)

        self.table_viewer = TableViewer(self, self.ui.tableView)

        self.current_image: np.ndarray = None  # 存储原始图像
        self.current_masks: np.ndarray = None  # 存储当前masks
        self.current_df: pd.DataFrame = None  # 存储当前df

        self.table_viewer.currentChanged.connect(self.tableView_currentChanged)

        self.model = InferenceModel()

    def setWindowTitle(self, title: str):
        super().setWindowTitle(f"Cellpose Deal - {title}")

    @Slot()
    def actionOpenFolder_triggered(self):
        folder_path = QFileDialog.getExistingDirectory(self, "打开文件夹")

        if folder_path:
            self.file_tree_viewer.setRootPath(folder_path)
            self.ui.menu_2.setEnabled(True)
            self.setWindowTitle(folder_path)

    @Slot()
    def actionModelConfig_triggered(self):
        print("actionModelConfig_triggered")
        # TODO

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

    @Slot(QModelIndex, QModelIndex)
    def treeView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        if previous.isValid():
            file_path = self.file_tree_viewer.filePath(previous)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("previous", file_path)

        self.ui.actionEvalCurrent.setEnabled(False)

        if current.isValid():
            file_path = self.file_tree_viewer.filePath(current)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("current", file_path)

                    pixmap = QPixmap(file_path)
                    self.image_viewer.set_pixmap(pixmap)

                    self.try_load_npy_csv(file_path)

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

    def try_load_npy_csv(self, file_path: str):
        basename = os.path.splitext(file_path)[0]
        npy_file = f"{basename}_seg.npy"
        csv_file = f"{basename}.csv"

        image = io.imread(file_path)
        masks = df = None

        if os.path.isfile(npy_file):
            npy: np.ndarray = np.load(npy_file, allow_pickle=True)
            d: dict = npy.item()
            masks: np.ndarray = d["masks"]

            overlay_image = draw_masks_on_image(image, masks)

            pixmap = numpy_to_qpixmap(overlay_image)

            self.image_viewer.set_pixmap(pixmap)

        if os.path.isfile(csv_file):
            df = pd.read_csv(csv_file)
            self.table_viewer.updateData(df)

        self.current_image = image
        self.current_masks = masks
        self.current_df = df

    @Slot(QModelIndex, QModelIndex)
    def tableView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        if self.current_masks is not None and self.current_df is not None:
            if current.isValid():
                row = current.row()
                particle_id = self.current_df.iloc[row, 0]
                self.highlight_particle(particle_id)

    def highlight_particle(self, particle_id: int):
        """
        高亮显示指定的颗粒
        """
        if self.current_masks is None or self.current_image is None:
            return

        # 创建高亮图像
        highlighted_image = draw_masks_on_image(
            self.current_image, self.current_masks, show_outlines=True
        )

        # 高亮选中的颗粒（用红色边框）
        mask = (self.current_masks == particle_id).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 确保图像是RGB
        if len(highlighted_image.shape) == 2:
            highlighted_image = cv2.cvtColor(highlighted_image, cv2.COLOR_GRAY2RGB)

        # 用红色粗线绘制选中的颗粒
        cv2.drawContours(highlighted_image, contours, -1, (255, 0, 0), 3)

        # 更新显示
        pixmap = numpy_to_qpixmap(highlighted_image)
        self.image_viewer.set_pixmap(pixmap)
