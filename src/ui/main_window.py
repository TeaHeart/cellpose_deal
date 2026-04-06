import os
import warnings
from PySide6.QtWidgets import QFileDialog, QGraphicsScene, QMainWindow
from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, Qt, Slot
from PySide6.QtGui import QColor, QImage, QPixmap, QWheelEvent
import cv2
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table
from ui.file_tree_viewer import FileTreeViewer
from ui.inference_model import InferenceModel
from ui.main_window_ui import Ui_MainWindow

warnings.filterwarnings("ignore", message="Sparse invariant checks")

IMAGE_EXTENSIONS = (".tif", ".tiff")


def overlay_masks_on_image(image: np.ndarray, masks: np.ndarray, alpha=0.5):
    """
    将mask叠加到原始图像上
    """
    # 确保图像是RGB格式
    if len(image.shape) == 2:
        # 灰度图转RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        image_rgb = image.copy()

    # 为每个mask生成随机颜色
    num_masks = masks.max()
    colors = np.random.randint(0, 255, size=(num_masks + 1, 3))
    colors[0] = [0, 0, 0]  # 背景为黑色

    # 创建彩色mask
    colored_masks = colors[masks]

    # 叠加图像
    overlay = cv2.addWeighted(image_rgb, 1 - alpha, colored_masks, alpha, 0)

    return overlay


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


def masks_to_dataframe(masks: np.ndarray, px_size: float):
    if masks.max() == 0:
        df = pd.DataFrame(
            columns=["颗粒ID", "直径", "圆度", "长宽比", "紧实度", "面积"]
        )
        return df

    props = regionprops_table(
        masks,
        properties=(
            "label",
            "area",
            "perimeter",
            "equivalent_diameter",
            "solidity",
            "major_axis_length",
            "minor_axis_length",
        ),
    )

    df = pd.DataFrame(props)

    # 计算衍生形态学指标
    df["圆度"] = 4 * np.pi * df["area"] / (df["perimeter"] ** 2)
    df["长宽比"] = df["major_axis_length"] / df["minor_axis_length"]
    df["直径"] = df["equivalent_diameter"] / px_size  # 转换为微米
    df["面积"] = df["area"] / (px_size**2)  # 转换为平方微米

    # 重命名列以符合输出要求
    df = df.rename(columns={"label": "颗粒ID", "solidity": "紧实度"})
    # 选择并排列输出列的顺序
    df = df[["颗粒ID", "直径", "圆度", "长宽比", "紧实度", "面积"]]

    return df


class PandasTableModel(QAbstractTableModel):
    """
    将Pandas DataFrame适配到QTableView的模型
    """

    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self._data = data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        value = self._data.iloc[index.row(), index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            # 格式化数值显示
            if isinstance(value, float):
                return f"{value:.3f}"
            return str(value)

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # 数值类型右对齐
            if isinstance(value, (int, float)):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.BackgroundRole:
            # 可选：根据数值设置背景色
            if isinstance(value, float):
                if value < 0.5:
                    return QColor(255, 200, 200)  # 浅红色
            return None

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            else:
                return str(self._data.index[section])
        return None

    def updateData(self, new_data: pd.DataFrame):
        """
        更新数据
        """
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle("Welcome")

        self.file_tree_viewer = FileTreeViewer(self, self.treeView)
        self.file_tree_viewer.currentChanged.connect(self.treeView_currentChanged)

        self.graphicsScene = QGraphicsScene(self)
        self.graphicsView.setScene(self.graphicsScene)
        self.graphicsView.installEventFilter(self)

        self.table_model: PandasTableModel = None
        self.current_image: np.ndarray = None  # 存储原始图像
        self.current_masks: np.ndarray = None  # 存储当前masks

        self.tableView.selectionModel().selectionChanged.connect(
            self.on_table_selection_changed
        )

        self.model = InferenceModel()

    def setWindowTitle(self, title: str):
        super().setWindowTitle(f"Cellpose Deal - {title}")

    @Slot()
    def on_action_open_folder_triggered(self):
        folder_path = QFileDialog.getExistingDirectory(self, "打开文件夹")

        if folder_path:
            self.file_tree_viewer.setRootPath(folder_path)

            self.setWindowTitle(folder_path)

    @Slot(QModelIndex, QModelIndex)
    def treeView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        if previous.isValid():
            file_path = self.file_tree_viewer.filePath(previous)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("previous", file_path)

        if current.isValid():
            file_path = self.file_tree_viewer.filePath(current)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("current", file_path)
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        self.image_viewer.set_pixmap(pixmap)

                        self.handler_file(file_path)

    def eventFilter(self, obj, event: QEvent):
        print(obj, event)
        if obj == self.graphicsView:
            if isinstance(event, QWheelEvent):
                # 缩放
                zoom_factor = 1.25
                if event.angleDelta().y() > 0:
                    self.graphicsView.scale(zoom_factor, zoom_factor)
                else:
                    self.graphicsView.scale(1 / zoom_factor, 1 / zoom_factor)
                return True

        return super().eventFilter(obj, event)

    def handler_file(self, file_path: str):
        px_size = 18.5

        # 执行分割
        print("执行分割...")
        image, masks, flows, styles = self.model.eval(file_path)
        print("分割完成...")

        self.current_image = image
        self.current_masks = masks

        # 计算DataFrame
        df = masks_to_dataframe(masks, px_size)

        # 显示DataFrame到tableView
        self.display_dataframe_to_tableview(df)

        # 显示带mask的图像
        self.display_image_with_masks(self.current_image, masks)

        # 打印统计信息
        print(f"检测到 {len(df)} 个颗粒")
        if len(df) > 0:
            print(f"平均直径: {df['直径'].mean():.2f} μm")
            print(f"平均圆度: {df['圆度'].mean():.3f}")

    def display_dataframe_to_tableview(self, df: pd.DataFrame):
        """
        将DataFrame显示到QTableView
        """
        if self.table_model is None:
            self.table_model = PandasTableModel(df)
            self.tableView.setModel(self.table_model)
        else:
            self.table_model.updateData(df)

        # 设置列宽自适应内容
        self.tableView.resizeColumnsToContents()

        # 设置选择模式
        self.tableView.setSelectionBehavior(self.tableView.SelectionBehavior.SelectRows)
        self.tableView.setSelectionMode(self.tableView.SelectionMode.SingleSelection)

    def display_image_with_masks(
        self, image: np.ndarray, masks: np.ndarray, mode="outline", alpha=0.5
    ):
        """
        显示带mask的图像

        Args:
            mode: "overlay" - 半透明叠加, "outline" - 轮廓线
            alpha: 透明度（仅对overlay模式有效）
        """
        if mode == "overlay":
            # 半透明叠加模式
            overlay_image = overlay_masks_on_image(image, masks, alpha)
        else:
            # 轮廓线模式（默认）
            overlay_image = draw_masks_on_image(image, masks, show_outlines=True)

        # 转换为QPixmap并显示
        pixmap = numpy_to_qpixmap(overlay_image)

        if not pixmap.isNull():
            self.graphicsScene.clear()
            self.graphicsScene.addPixmap(pixmap)
            self.graphicsScene.setSceneRect(pixmap.rect())
            self.graphicsView.fitInView(
                self.graphicsScene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def on_table_selection_changed(self, selected, deselected):
        """
        当在表格中选择颗粒时，高亮显示对应的mask
        """
        if not self.current_masks is not None:
            return

        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            # 获取颗粒ID（假设第一列是ID）
            particle_id = self.table_model._data.iloc[row, 0]

            # 高亮显示选中的颗粒
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
        if not pixmap.isNull():
            self.graphicsScene.clear()
            self.graphicsScene.addPixmap(pixmap)
            self.graphicsScene.setSceneRect(pixmap.rect())
            self.graphicsView.fitInView(
                self.graphicsScene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )
