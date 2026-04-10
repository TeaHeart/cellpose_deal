from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QGraphicsSceneMouseEvent, QMenu
from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal, Slot, QPoint
from PySide6.QtGui import QBrush, QPen, QPixmap, QWheelEvent, QMouseEvent
import cv2
import numpy as np


class ImageViewer(QObject):
    contourClicked = Signal(int)  # 发射被点击的 cell label
    deleteToggled = Signal(int, bool)  # label, is_deleted
    def __init__(self, parent: QObject, graphicsView: QGraphicsView):
        super().__init__(parent)
        self._graphicsView = graphicsView

        self._graphicsScene = QGraphicsScene(self)

        self._graphicsView.setScene(self._graphicsScene)
        self._graphicsView.installEventFilter(self)

        # 启用右键菜单
        self._graphicsView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._graphicsView.customContextMenuRequested.connect(self._show_context_menu)

        # 新增成员
        self._masks: np.ndarray | None = None
        self._contours: dict[int, object] = {}
        self._selected_label: int | None = None
        self._deleted_labels: set[int] = set()

        # 颜色定义
        self._green_pen = QPen(Qt.GlobalColor.green, 2)
        self._yellow_pen = QPen(Qt.GlobalColor.yellow, 2)
        self._red_pen = QPen(Qt.GlobalColor.red, 2)

    def eventFilter(self, watched: QObject, event: QEvent):
        if watched == self._graphicsView:
            if isinstance(event, QWheelEvent):
                # 滚轮缩放功能
                zoom_factor = 1.25
                if event.angleDelta().y() > 0:
                    self._graphicsView.scale(zoom_factor, zoom_factor)
                else:
                    self._graphicsView.scale(1 / zoom_factor, 1 / zoom_factor)
                return True

        return super().eventFilter(watched, event)

    def set_pixmap(self, pixmap: QPixmap):
        if not pixmap.isNull():
            self._graphicsScene.clear()
            self._contours.clear()
            self._masks = None
            self._selected_label = None
            self._deleted_labels.clear()

            self._graphicsScene.addPixmap(pixmap)
            self._graphicsScene.setSceneRect(pixmap.rect())
            self._graphicsView.fitInView(
                self._graphicsScene.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

            # 连接鼠标点击事件
            self._graphicsScene.mousePressEvent = self._on_scene_mouse_press

    def draw_contours(self, masks: np.ndarray, show_label=True):
        """绘制轮廓并保存引用"""
        self._masks = masks
        self._contours.clear()
        self._deleted_labels.clear()
        self._selected_label = None

        red_brush = QBrush(Qt.GlobalColor.red)
        green_pen = QPen(Qt.GlobalColor.green, 2)

        # 为每个颗粒绘制轮廓
        for label in range(1, masks.max() + 1):
            QApplication.processEvents() # 临时解决
            mask = (masks == label).astype(np.uint8)
            # [第几个(1), 点数量, 1, (x,y)]
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            contours: tuple[np.ndarray]

            # 绘制轮廓
            if contours:
                points = contours[0].reshape(-1, 2)
                pointfs = [QPointF(x, y) for x, y in points]
                item = self._graphicsScene.addPolygon(pointfs)
                item.setPen(green_pen)
                self._contours[label] = item

            # 绘制标签
            if show_label:
                moment = cv2.moments(mask)
                if moment["m00"] != 0:
                    cx = int(moment["m10"] / moment["m00"])
                    cy = int(moment["m01"] / moment["m00"])

                    item = self._graphicsScene.addSimpleText(str(label))
                    item.setPos(cx, cy)
                    item.setBrush(red_brush)

    def _on_scene_mouse_press(self, event: QGraphicsSceneMouseEvent):
        """处理场景鼠标点击"""
        if self._masks is None:
            return

        # 获取点击位置（场景坐标）
        pos = event.scenePos()
        x, y = int(pos.x()), int(pos.y())

        # 检查边界
        h, w = self._masks.shape
        if not (0 <= x < w and 0 <= y < h):
            return

        # 获取点击位置的 label
        label = int(self._masks[y, x])
        if label > 0:
            self._select_contour(label)
            self.contourClicked.emit(label)

    def _select_contour(self, label: int):
        """选中指定轮廓"""
        # 恢复之前选中的轮廓颜色
        if self._selected_label and self._selected_label in self._contours:
            self._update_contour_color(self._selected_label)

        self._selected_label = label

        # 设置新选中轮廓为红色
        if label in self._contours:
            self._contours[label].setPen(self._red_pen)

    def _update_contour_color(self, label: int):
        """根据删除状态更新轮廓颜色"""
        if label not in self._contours:
            return

        # 选中状态优先级最高
        if label == self._selected_label:
            self._contours[label].setPen(self._red_pen)
        elif label in self._deleted_labels:
            self._contours[label].setPen(self._yellow_pen)
        else:
            self._contours[label].setPen(self._green_pen)

    @Slot(int, bool)
    def set_deleted(self, label: int, deleted: bool):
        """设置轮廓删除状态（由外部调用）"""
        if deleted:
            self._deleted_labels.add(label)
        else:
            self._deleted_labels.discard(label)
        self._update_contour_color(label)

    def _get_label_at_pos(self, pos: QPoint) -> int | None:
        """获取右键点击位置的细胞 label"""
        if self._masks is None:
            return None

        # 将视图坐标转换为场景坐标
        scene_pos = self._graphicsView.mapToScene(pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())

        h, w = self._masks.shape
        if not (0 <= x < w and 0 <= y < h):
            return None

        label = int(self._masks[y, x])
        return label if label > 0 else None

    @Slot(QPoint)
    def _show_context_menu(self, position: QPoint):
        """显示右键菜单"""
        label = self._get_label_at_pos(position)
        if label is None:
            return

        is_deleted = label in self._deleted_labels

        menu = QMenu()
        if is_deleted:
            action = menu.addAction("取消删除")
            action.triggered.connect(lambda: self.deleteToggled.emit(label, False))
        else:
            action = menu.addAction("标记删除")
            action.triggered.connect(lambda: self.deleteToggled.emit(label, True))

        menu.exec(self._graphicsView.viewport().mapToGlobal(position))
