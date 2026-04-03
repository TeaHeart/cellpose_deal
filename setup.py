from setuptools import setup, Command
import subprocess
import os


class BuildUi(Command):
    description = "Compile .ui and .qrc files"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # 编译文件
        for root, dirs, files in os.walk("src"):
            for file in files:
                if file.endswith(".ui"):
                    ui_path = os.path.join(root, file)
                    py_path = ui_path.replace(".ui", "_ui.py")
                    result = subprocess.run(
                        ["pyside6-uic", ui_path, "-o", py_path, "--absolute-imports"],
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode == 0:
                        print(f"✅ 成功编译: {ui_path} -> {py_path}")
                    else:
                        print(f"❌️ 编译失败: {ui_path}")
                        print(f"❗️ 错误信息: {result.stderr}")
                        raise Exception(f"{ui_path} {result.stderr}")

                elif file.endswith(".qrc"):
                    qrc_path = os.path.join(root, file)
                    py_path = qrc_path.replace(".qrc", "_rc.py")
                    result = subprocess.run(
                        ["pyside6-rcc", qrc_path, "-o", py_path],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        print(f"✅️ 成功编译: {qrc_path} -> {py_path}")
                    else:
                        print(f"❌️ 编译失败: {qrc_path}")
                        print(f"❗️ 错误信息: {result.stderr}")
                        raise Exception(f"{qrc_path} {result.stderr}")


setup(
    name="cellpose_deal",
    cmdclass={
        "build_ui": BuildUi,
    },
)
