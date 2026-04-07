import numpy as np
import pandas as pd
from typing import TypedDict
from cellpose import models, io
from PySide6.QtCore import QThread, Signal
from skimage.measure import regionprops_table


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
    ) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], np.ndarray, pd.DataFrame]:
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
        df = masks_to_dataframe(masks, px_size)

        return image, masks, flows, styles, df


class InferenceResult(TypedDict):
    success: bool
    file: str
    error: Exception | None
    image: np.ndarray | None
    masks: np.ndarray | None
    flows: list[np.ndarray] | None
    styles: np.ndarray | None
    df: pd.DataFrame | None


class InferenceWorker(QThread):
    # 进度值, 总数量, 当前文件
    progress_updated = Signal(int, int, str)
    # 单个文件完成
    file_completed = Signal(InferenceResult)
    # 全部完成
    all_finished = Signal(list)  # list[InferenceResult]
    # 文件名, 错误信息
    error_occurred = Signal(str, Exception)

    def __init__(self, model: InferenceModel, files: list[str]):
        super().__init__()
        self.model = model
        self.files = files
        self._is_canceled = False

    def cancel(self):
        self._is_canceled = True

    def run(self):
        results: list[InferenceResult] = []
        total = len(self.files)

        for i, file in enumerate(self.files):
            if self._is_canceled:
                return

            self.progress_updated.emit(i, total, file)

            try:
                image, masks, flows, styles, df = self.model.eval(file)

                if self._is_canceled:
                    raise Exception("用户取消操作")

                result: InferenceResult = {
                    "success": True,
                    "file": file,
                    "image": image,
                    "masks": masks,
                    "flows": flows,
                    "styles": styles,
                    "df": df,
                }
                results.append(result)
                self.file_completed.emit(result)
            except Exception as e:
                results.append({"success": False, "file": file, "error": e})
                self.error_occurred.emit(file, e)

        self.progress_updated.emit(total, total, None)
        self.all_finished.emit(results)
