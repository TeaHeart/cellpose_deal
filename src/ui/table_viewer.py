import pandas as pd
from PySide6.QtWidgets import QTableView, QMenu
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
    QPoint,
    QItemSelectionModel,
)
from PySide6.QtGui import QColor


class PandasTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._data = pd.DataFrame()

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
                return f"{value:.4f}"
            return str(value)

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # 数值类型右对齐
            if isinstance(value, (int, float)):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.ForegroundRole:
            # 已删除的行显示为黄色
            if self.is_deleted(index.row()):
                return QColor(Qt.GlobalColor.yellow)

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

    def updateData(self, data: pd.DataFrame):
        self.beginResetModel()
        self._data = data
        self._ensure_deleted_column()
        self.endResetModel()

    def _ensure_deleted_column(self):
        """确保数据包含 已删除 列，不存在则添加"""
        if "已删除" not in self._data.columns:
            self._data["已删除"] = False

    def set_deleted(self, row: int, deleted: bool):
        """设置行的删除状态"""
        if row < 0 or row >= len(self._data):
            return
        self._ensure_deleted_column()
        self._data.iloc[row, self._data.columns.get_loc("已删除")] = deleted
        # 通知视图更新
        top_left = self.index(row, 0)
        col_count = self.columnCount()
        if col_count > 0:
            bottom_right = self.index(row, col_count - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def is_deleted(self, row: int) -> bool:
        """查询行是否被标记删除"""
        if row < 0 or row >= len(self._data):
            return False
        self._ensure_deleted_column()
        return bool(self._data.iloc[row]["已删除"])

    def save_to_csv(self, path: str):
        """保存数据到 CSV（保留 已删除 列）"""
        self._ensure_deleted_column()
        self._data.to_csv(path, index=False, encoding="utf-8-sig")


class TableViewer(QObject):
    currentChanged = Signal(QModelIndex, QModelIndex)
    deleteToggled = Signal(int, bool)  # row, is_deleted
    generateCsvRequested = Signal()  # 请求生成csv

    def __init__(self, parent: QObject, tableView: QTableView):
        super().__init__(parent)
        self._tableView = tableView

        self._tableViewModel = PandasTableModel(self)
        self._tableView.setModel(self._tableViewModel)

        self._tableViewSelectionModel = self._tableView.selectionModel()
        self._tableViewSelectionModel.currentChanged.connect(self.currentChanged)

        # 启用右键菜单
        self._tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tableView.customContextMenuRequested.connect(self._show_context_menu)

    def updateData(self, data: pd.DataFrame):
        self._tableViewModel.updateData(data)

    def data(self, row: int, column: int):
        return self._tableViewModel._data.iloc[row, column]

    def selectRow(self, row: int):
        """选中指定行"""
        if row < 0 or row >= self._tableViewModel.rowCount(QModelIndex()):
            return
        index = self._tableViewModel.index(row, 0)
        self._tableView.selectionModel().setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self._tableView.scrollTo(index)

    @Slot(QPoint)
    def _show_context_menu(self, position: QPoint):
        """显示右键菜单"""
        index = self._tableView.indexAt(position)
        if not index.isValid():
            return

        row = index.row()
        is_deleted = self._tableViewModel.is_deleted(row)

        menu = QMenu()

        # 根据状态显示不同选项
        if is_deleted:
            action = menu.addAction("取消删除")
            action.triggered.connect(lambda: self._toggle_delete(row, False))
        else:
            action = menu.addAction("标记删除")
            action.triggered.connect(lambda: self._toggle_delete(row, True))

        # 重新生成csv
        generate_csv_action = menu.addAction("重新生成csv")
        generate_csv_action.triggered.connect(self.generateCsvRequested.emit)

        menu.addSeparator()

        menu.exec(self._tableView.viewport().mapToGlobal(position))

    def _toggle_delete(self, row: int, deleted: bool):
        """切换删除状态"""
        self._tableViewModel.set_deleted(row, deleted)
        self.deleteToggled.emit(row, deleted)
