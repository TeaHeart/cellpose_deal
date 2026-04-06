from PySide6.QtWidgets import QFileSystemModel, QTreeView
from PySide6.QtCore import QModelIndex, QObject, Signal, Slot


class FileTreeViewer(QObject):
    currentChanged = Signal(QModelIndex, QModelIndex)

    def __init__(self, parent: QObject, treeView: QTreeView):
        super().__init__(parent)
        self._treeView = treeView

        self._treeViewModel = QFileSystemModel(self)
        # 文件过滤
        self._treeViewModel.directoryLoaded.connect(self._treeViewModel_directoryLoaded)

        # 隐藏类型和时间列
        self._treeView.setModel(self._treeViewModel)
        self._treeView.hideColumn(2)
        self._treeView.hideColumn(3)
        self._treeView.clicked.connect(self._treeView_clicked)

        # 文件选择
        self._treeViewSelectionModel = self._treeView.selectionModel()
        self._treeViewSelectionModel.currentChanged.connect(self.currentChanged)

    @Slot(QModelIndex)
    def _treeView_clicked(self, clicked: QModelIndex):
        # 单击展开/关闭
        if clicked.isValid():
            isExpanded = self._treeView.isExpanded(clicked)
            self._treeView.setExpanded(clicked, not isExpanded)

    @Slot(str)
    def _treeViewModel_directoryLoaded(self, path: str):
        # 展开并调整列宽
        self._treeView.expandToDepth(1)
        self._treeView.resizeColumnToContents(0)

    def filePath(self, index: QModelIndex):
        return self._treeViewModel.filePath(index)

    def setRootPath(self, path: str):
        root_index = self._treeViewModel.setRootPath(path)
        self._treeView.setRootIndex(root_index)
