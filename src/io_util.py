import os
from datetime import datetime
from timer_util import timer_decorator


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
