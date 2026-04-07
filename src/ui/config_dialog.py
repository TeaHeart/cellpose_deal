from PySide6.QtWidgets import QDialog
from ui.config_dialog_ui import Ui_ConfigDialog
from ui.inference_model import InferenceConfig


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ConfigDialog()
        self.ui.setupUi(self)

    @property
    def config(self) -> InferenceConfig:
        return {
            "px_size": self.ui.doubleSpinBox_px_size.value(),
            "diam": self.ui.doubleSpinBox_diam.value(),
            "niter": self.ui.spinBox_niter.value(),
        }

    @config.setter
    def config(self, value: InferenceConfig):
        self.ui.doubleSpinBox_px_size.setValue(value["px_size"])
        self.ui.doubleSpinBox_diam.setValue(value["diam"])
        self.ui.spinBox_niter.setValue(value["niter"])
