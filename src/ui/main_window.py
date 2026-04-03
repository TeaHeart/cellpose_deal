from PySide6.QtWidgets import QFileDialog, QMainWindow, QFileSystemModel
from PySide6.QtCore import Slot
from ui.main_window_ui import Ui_MainWindow


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.set_topic("细胞处理")

        self.treeView_model = QFileSystemModel()
        self.treeView.setModel(self.treeView_model)
        # 设置名称列宽度
        self.treeView.setColumnWidth(0, 200)
        # 隐藏类型和时间列
        self.treeView.hideColumn(2)
        self.treeView.hideColumn(3)

    def set_topic(self, topic: str = None):
        self.setWindowTitle(f"Cellpose Deal - {topic}")

    @Slot()
    def on_action_open_folder_triggered(self):
        folder_path = QFileDialog.getExistingDirectory(self, "打开文件夹")

        if folder_path:
            root_index = self.treeView_model.setRootPath(folder_path)
            self.treeView.setRootIndex(root_index)

            self.set_topic(folder_path)
