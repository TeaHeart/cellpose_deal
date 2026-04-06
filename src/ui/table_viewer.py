import pandas as pd
from PySide6.QtWidgets import QTableView
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, Signal


class PandasTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._data = pd.DataFrame()

    def rowCount(self, parent: QModelIndex):
        return len(self._data)

    def columnCount(self, parent: QModelIndex):
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
        self.endResetModel()


class TableViewer(QObject):
    currentChanged = Signal(QModelIndex, QModelIndex)

    def __init__(self, parent: QObject, tableView: QTableView):
        super().__init__(parent)
        self._tableView = tableView

        self._tableViewModel = PandasTableModel(self)
        self._tableView.setModel(self._tableViewModel)

        self._tableViewSelectionModel = self._tableView.selectionModel()
        self._tableViewSelectionModel.currentChanged.connect(self.currentChanged)

    def updateData(self, data: pd.DataFrame):
        self._tableViewModel.updateData(data)
        self._tableView.resizeColumnsToContents()
