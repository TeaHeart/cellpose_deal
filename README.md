# Cellpose Deal - 细胞分割质检工具

基于 Cellpose 的桌面端图像分割与质检工具，为科研人员提供从原始图片批量处理、交互式审查到结构化数据导出的完整本地化工作流。

## 功能特性

- **批量处理**：递归扫描文件夹，批量处理图像
- **可视化**：可视化查看分割结果，轮廓叠加显示，选中高亮
- **数据保存**：自动保存npy，csv和yaml文件

![demo](./docs/demo.png)

## 如何运行

### 环境要求

> 开发测试用的以下环境

- Python 3.11
- requirements.txt
- torch==2.11.0+cu128

### 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv
# 激活虚拟环境(后续都是在虚拟环境操作)
.venv\Scripts\activate     # Windows

# 安装依赖, 使用阿里云镜像的torch, 若无cuda手动安装CPU版的torch即可
pip install -r .\requirements.txt -f https://mirrors.aliyun.com/pytorch-wheels/cu128/
```

### 启动方式

- 命令启动(或使用vscode的launch和task启动)

```bash
# GUI
python setup.py build_ui
python src/main_gui.py
# CLI
python src/main_cli.py
# cellpose 的 GUI
cellpose.exe
```
