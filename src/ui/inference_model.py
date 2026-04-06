import numpy as np
from cellpose import models, io


class InferenceModel:
    def __init__(self):
        self.__model = None

    @property
    def _model(self):
        if self.__model is None:
            print("加载模型...")
            self.__model = models.CellposeModel(gpu=True)
            print("加载完成...")

        return self.__model

    def eval(
        self, file_path: str
    ) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], np.ndarray]:
        # TODO 提取配置
        px_size = 18.5
        diam = 100
        niter = None

        image = io.imread(file_path)
        masks, flows, styles = self._model.eval(
            x=image,
            diameter=diam,
            niter=niter,
        )

        return image, masks, flows, styles
