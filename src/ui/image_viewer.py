from PySide6.QtWidgets import QGraphicsScene, QGraphicsView
from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QBrush, QPen, QPixmap, QWheelEvent
import cv2
import numpy as np


class ImageViewer(QObject):
    def __init__(self, parent: QObject, graphicsView: QGraphicsView):
        super().__init__(parent)
        self._graphicsView = graphicsView

        self._graphicsScene = QGraphicsScene(self)

        self._graphicsView.setScene(self._graphicsScene)
        self._graphicsView.installEventFilter(self)

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
            self._graphicsScene.addPixmap(pixmap)
            self._graphicsScene.setSceneRect(pixmap.rect())
            self._graphicsView.fitInView(
                self._graphicsScene.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

    def draw_contours(self, masks: np.ndarray, show_label=True):
        red_brush = QBrush(Qt.GlobalColor.red)
        green_pen = QPen(Qt.GlobalColor.green, 2)

        # 为每个颗粒绘制轮廓
        for label in range(1, masks.max() + 1):

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
                yield label, item

            # 绘制标签
            if show_label:
                moment = cv2.moments(mask)
                if moment["m00"] != 0:
                    cx = int(moment["m10"] / moment["m00"])
                    cy = int(moment["m01"] / moment["m00"])

                    item = self._graphicsScene.addSimpleText(str(label))
                    item.setPos(cx, cy)
                    item.setBrush(red_brush)
