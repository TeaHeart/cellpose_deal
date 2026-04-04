import os
from PySide6.QtWidgets import QFileDialog, QGraphicsScene, QMainWindow, QFileSystemModel
from PySide6.QtCore import QEvent, QModelIndex, Qt, Slot
from PySide6.QtGui import QPixmap, QWheelEvent
from ui.main_window_ui import Ui_MainWindow

IMAGE_EXTENSIONS = (".tif", ".tiff")


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle("Welcome")

        self.treeView_model = QFileSystemModel()
        self.treeView_model.directoryLoaded.connect(self.treeView_directoryLoaded)
        self.treeView.setModel(self.treeView_model)

        # 隐藏类型和时间列
        self.treeView.hideColumn(2)
        self.treeView.hideColumn(3)

        self.treeView_selectionModel = self.treeView.selectionModel()
        self.treeView_selectionModel.currentChanged.connect(
            self.treeView_currentChanged
        )

        self.graphicsScene = QGraphicsScene(self)
        self.graphicsView.setScene(self.graphicsScene)
        self.graphicsView.installEventFilter(self)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(f"Cellpose Deal - {title}")

    @Slot()
    def on_action_open_folder_triggered(self):
        folder_path = QFileDialog.getExistingDirectory(self, "打开文件夹")

        if folder_path:
            root_index = self.treeView_model.setRootPath(folder_path)
            self.treeView.setRootIndex(root_index)

            self.setWindowTitle(folder_path)

    @Slot(QModelIndex)
    def on_treeView_clicked(self, clicked: QModelIndex):
        # 单击展开/关闭
        if clicked.isValid():
            isExpanded = self.treeView.isExpanded(clicked)
            self.treeView.setExpanded(clicked, not isExpanded)

    @Slot(str)
    def treeView_directoryLoaded(self, path: str):
        self.treeView.expandToDepth(1)
        self.treeView.resizeColumnToContents(0)

    @Slot(QModelIndex, QModelIndex)
    def treeView_currentChanged(self, current: QModelIndex, previous: QModelIndex):
        if previous.isValid():
            file_path = self.treeView_model.filePath(previous)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("previous", file_path)

        if current.isValid():
            file_path = self.treeView_model.filePath(current)
            if os.path.isfile(file_path):
                if file_path.lower().endswith(IMAGE_EXTENSIONS):
                    print("current", file_path)
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        # 清除之前的图片
                        self.graphicsScene.clear()
                        # 添加新图片
                        self.graphicsScene.addPixmap(pixmap)
                        # 设置场景矩形为图片大小
                        self.graphicsScene.setSceneRect(pixmap.rect())
                        # 自动适配视图
                        self.graphicsView.fitInView(
                            self.graphicsScene.sceneRect(), Qt.KeepAspectRatio
                        )

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
