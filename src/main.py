import os
import shutil
import yaml
from datetime import datetime
from cellpose_util import *


@timer_decorator
def list_images(
    start_path: str,
    exts: list[str] = None,  # 图片后缀
    depth: int | None = None,
):
    if exts is None:
        exts = [".tif", ".tiff"]

    # 标准化扩展名
    exts = [ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in exts]

    # 获取起始路径的深度级别
    start_depth = start_path.rstrip(os.sep).count(os.sep)

    for root, dirs, files in os.walk(start_path):
        # 计算当前深度
        current_depth = root.rstrip(os.sep).count(os.sep) - start_depth

        # 检查是否超出深度限制
        if depth is not None and current_depth > depth:
            # 超出深度时，清空 dirs 以避免继续深入遍历
            dirs.clear()
            continue

        for file in files:
            # 检查文件扩展名（不区分大小写）
            if os.path.splitext(file)[1].lower() in exts:
                file_path = os.path.join(root, file)
                group = os.path.relpath(root, start=start_path)
                yield file_path, root, group


@timer_decorator
def enum_output_dirs(images: list[(str, str, str)]):
    # 创建目录，格式如 output_yyyyMMdd_hhmmss
    output = datetime.now().strftime(f"output{os.sep}%Y%m%d_%H%M%S")
    os.makedirs(output, exist_ok=True)

    for file, parent, group in images:
        # 为每个图片创建指定的目录结构
        image_name = os.path.splitext(os.path.basename(file))[0]
        segpkg_dir = os.path.join(output, group, f"{image_name}.segpkg")

        # 创建子目录
        raw_dir = os.path.join(segpkg_dir, "1_原始数据")
        process_dir = os.path.join(segpkg_dir, "2_处理结果")
        result_dir = os.path.join(segpkg_dir, "3_最终结果")

        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(process_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        yield raw_dir, process_dir, result_dir


def main():
    if True:
        while True:
            input_dir = input("请输入目录: ").strip(" '\"")
            if os.path.isdir(input_dir):
                break
            else:
                print("输入的路径不正确")
    else:
        input_dir = "test_data"

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

        cellpose_config = config["cellpose"]
        px_size = cellpose_config["px_size"]
        diam = cellpose_config["diam"]

    model = models.CellposeModel(gpu=True)

    image_path_list = list(list_images(input_dir))
    image_list = [io.imread(file) for file, parent, group in image_path_list]
    output_dirs_list = list(enum_output_dirs(image_path_list))

    masks_list, flows_list, styles_list = eval_images(
        image_list,
        model,
        diam=diam,
    )

    df_list = [masks_to_dataframe(masks, px_size) for masks in masks_list]

    for i in range(len(image_path_list)):
        image_path, image_parent, image_group = image_path_list[i]
        image = image_list[i]
        raw_dir, process_dir, result_dir = output_dirs_list[i]
        masks, flows, styles, df = (
            masks_list[i],
            flows_list[i],
            styles_list[i],
            df_list[i],
        )

        # 复制原始图片
        copy_image_path = os.path.join(raw_dir, "原始图片.tif")
        shutil.copy(image_path, copy_image_path)

        # 保存遮罩和cvs
        full_masks = os.path.join(process_dir, "完整遮罩.npy")
        io.masks_flows_to_seg(image, masks, flows, full_masks)

        full_cvs = os.path.join(process_dir, "完整记录.cvs")
        df.to_csv(full_cvs)

        # 保存筛选后的遮罩和cvs
        # 暂无实现


if __name__ == "__main__":
    main()
