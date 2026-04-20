from setuptools import setup, Command
from distutils.errors import DistutilsExecError
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


class FormatCode(Command):
    description = "Format Python files using Black"
    user_options = [
        ("check", "c", "Check only, don't format"),
    ]

    def initialize_options(self):
        self.check = False

    def finalize_options(self):
        self.check = bool(self.check)

    def run(self):
        cmd = ["black"]
        if self.check:
            cmd.append("--check")

        files = []
        for root, dirs, files_in_dir in os.walk("src"):
            for file in files_in_dir:
                if file.endswith(".py"):
                    if not file.endswith(("_ui.py", "_rc.py")):
                        files.append(os.path.join(root, file))

        if files:
            cmd.extend(files)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="unicode-escape",
                errors="ignore",
            )

            if result.returncode == 0:
                print(result.stderr)
            else:
                raise DistutilsExecError(f"FormatCode failed: {result.stderr}")
        else:
            print("没有找到需要格式化的py文件")


setup(
    name="cellpose_deal",
    cmdclass={
        "build_ui": BuildUi,
        "format": FormatCode,
    },
)
