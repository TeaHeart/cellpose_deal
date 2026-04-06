from PySide6.QtWidgets import QGraphicsScene, QGraphicsView
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QPixmap, QWheelEvent


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
