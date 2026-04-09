import os
import shutil
from cellpose import io, models
import yaml
from cellpose_util import eval_images, masks_to_dataframe
from io_util import enum_output_dirs, list_images


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
        niter = cellpose_config["niter"]

    model = models.CellposeModel(gpu=True)

    image_path_list = list(list_images(input_dir))
    image_list = [io.imread(file) for file, parent, group in image_path_list]
    output_dirs_list = list(enum_output_dirs(image_path_list))

    masks_list, flows_list, styles_list = eval_images(
        image_list,
        model,
        diam=diam,
        niter=niter
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
