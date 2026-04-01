import os
import numpy as np
import pandas as pd
from cellpose import models, io
from skimage.measure import regionprops_table
import configparser
import warnings

warnings.filterwarnings("ignore", message="Sparse invariant checks")

def eval_image(
    image,                          # 图片
    model: models.CellposeModel,    # 模型
    px_size=18.535,                 # 标尺 (px/μm)
    diam=100,                       # 预估直径(像素)
    flow=0.4,                       # 流场阈值
    cellprob=0.0,                   # 细胞概率阈值
    niter=200,                      # 迭代次数
):
    outputs = model.eval(
        x=image,
        diameter=diam,
        flow_threshold=flow,
        cellprob_threshold=cellprob,
        normalize=True,
        niter=niter
    )

    masks, flows, styles = outputs

    if masks.max() == 0:
        df = pd.DataFrame(columns=['颗粒ID', '直径', '圆度', '长宽比', '紧实度', '面积'])
        return masks, flows, styles, df

    props = regionprops_table(
        masks,
        properties=(
            'label', 'area', 'perimeter', 'equivalent_diameter',
            'solidity', 'major_axis_length', 'minor_axis_length'
        )
    )

    df = pd.DataFrame(props)

    # 计算衍生形态学指标
    df['圆度'] = 4 * np.pi * df['area'] / (df['perimeter']**2)
    df['长宽比'] = df['major_axis_length'] / df['minor_axis_length']
    # px_size 单位为 px/µm，需取倒数转换为 µm/px
    um_per_px = 1 / px_size
    df['直径'] = df['equivalent_diameter'] * um_per_px          # 转换为微米
    df['面积'] = df['area'] * (um_per_px**2)                    # 转换为平方微米

    # 重命名列以符合输出要求
    df = df.rename(columns={'label': '颗粒ID', 'solidity': '紧实度'})
    # 选择并排列输出列的顺序
    df = df[['颗粒ID', '直径', '圆度', '长宽比', '紧实度', '面积']]

    return masks, flows, styles, df

def analyze_gel_batch(input_dir: str, config: configparser.SectionProxy):
    model = models.CellposeModel(gpu=True)  # 启用 GPU 加速

    px_size = float(config.get('px_size', 0.5))
    diam = config.getint('diam', None)

    xlsx_path = os.path.join(input_dir, 'output.xlsx')

    with pd.ExcelWriter(xlsx_path, mode='w') as writer:
        # 一级目录 Day xxx
        for day in os.listdir(input_dir):
            level1 = os.path.join(input_dir, day)
            if os.path.isfile(level1):
                continue
            # 二级目录 xxx%
            for percent in os.listdir(level1):
                level2 = os.path.join(level1, percent)
                if os.path.isfile(level2):
                    continue
                # 图片
                total = 0
                all_dfs = []  # 收集该二级目录下所有图片的数据
                for file in os.listdir(level2):
                    full_path = os.path.join(level2, file)
                    if os.path.isfile(full_path) and file.lower().endswith(('.tif', '.tiff')):
                        print('处理', full_path)
                        image = io.imread(full_path)

                        masks, flows, styles, df = eval_image(
                            image=image,
                            model=model,
                            px_size=px_size,
                            diam=diam
                        )

                        io.masks_flows_to_seg(images=image, masks=masks, flows=flows, file_names=full_path)
                        print(f'写入 npy {file}')
                        total += masks.max()

                        all_dfs.append(df)

                # 合并该二级目录下所有图片的数据
                if all_dfs:
                    combined_df = pd.concat(all_dfs, ignore_index=True)
                    sheet_name = f'{day}_{percent}'
                    combined_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f'写入 sheet: {sheet_name}, 共 {len(combined_df)} 个颗粒')

                print(f'>>> {level2} 共有 {total} 个')

if __name__ == "__main__":
    print("=== 凝胶颗粒批量分析工具 ===")
    p_root = input("请输入【项目根目录】路径：").strip('"')

    configParser = configparser.ConfigParser()
    configParser.read('config.ini', encoding='utf-8')
    config = configParser['DEFAULTS']

    if p_root:
        analyze_gel_batch(p_root, config)
    else:
        print("路径不能为空！")
