import numpy as np
import pandas as pd
from cellpose import models, io
from skimage.measure import regionprops_table
from timer_util import timer_decorator
import warnings


warnings.filterwarnings("ignore", message="Sparse invariant checks")


@timer_decorator
def masks_to_dataframe(masks, px_size: float):
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


@timer_decorator
def eval_images(
    image_list: list,  # 图片
    model: models.CellposeModel,  # 模型
    diam=100,  # 预估直径(像素)
    flow=0.4,  # 流场阈值
    cellprob=0.0,  # 细胞概率阈值
    niter=200,  # 迭代次数
):
    return model.eval(
        x=image_list,
        diameter=diam,
        flow_threshold=flow,
        cellprob_threshold=cellprob,
        normalize=True,
        niter=niter,
    )
