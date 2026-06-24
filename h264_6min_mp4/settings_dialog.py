from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from .conversion_controller import ConversionSettings, ExistingOutputPolicy

# [H264APP_P0002] begin


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conversion settings")
        self.setModal(True)
        self.setMinimumWidth(330)

        self._settings_store = QSettings(
            "Cricket Neuroethology Lab",
            "H264 6-Minute MP4",
        )

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 36_000)
        self.duration_spin.setSuffix(" sec")

        self.output_subfolder_edit = QLineEdit()

        self.jobs_combo = QComboBox()
        self.jobs_combo.addItems(["1", "2", "4", "6"])

        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.0, 60.0)
        self.tolerance_spin.setDecimals(3)
        self.tolerance_spin.setSingleStep(0.01)
        self.tolerance_spin.setSuffix(" sec")

        self.skip_radio = QRadioButton("Skip")
        self.overwrite_radio = QRadioButton("Overwrite")
        self.stop_radio = QRadioButton("Stop and report")

        self.policy_group = QButtonGroup(self)
        for button in (
            self.skip_radio,
            self.overwrite_radio,
            self.stop_radio,
        ):
            self.policy_group.addButton(button)

        self.create_log_checkbox = QCheckBox("Create conversion_log.tsv")

        policy_layout = QVBoxLayout()
        policy_layout.setContentsMargins(0, 0, 0, 0)
        policy_layout.addWidget(self.skip_radio)
        policy_layout.addWidget(self.overwrite_radio)
        policy_layout.addWidget(self.stop_radio)

        form = QFormLayout()
        form.addRow("Target duration", self.duration_spin)
        form.addRow("Output subfolder", self.output_subfolder_edit)
        form.addRow("Parallel jobs", self.jobs_combo)
        form.addRow("Existing outputs", policy_layout)
        form.addRow("Validation tolerance", self.tolerance_spin)
        form.addRow("", self.create_log_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save_and_accept)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

        self._load_values()

    def conversion_settings(self) -> ConversionSettings:
        policy = ExistingOutputPolicy.SKIP
        if self.overwrite_radio.isChecked():
            policy = ExistingOutputPolicy.OVERWRITE
        elif self.stop_radio.isChecked():
            policy = ExistingOutputPolicy.STOP

        return ConversionSettings(
            target_seconds=self.duration_spin.value(),
            output_subfolder=self.output_subfolder_edit.text().strip(),
            parallel_jobs=int(self.jobs_combo.currentText()),
            existing_policy=policy,
            tolerance_seconds=self.tolerance_spin.value(),
            create_log=self.create_log_checkbox.isChecked(),
        )

    def _load_values(self) -> None:
        self.duration_spin.setValue(
            self._settings_store.value("target_seconds", 360, int)
        )
        self.output_subfolder_edit.setText(
            self._settings_store.value(
                "output_subfolder",
                "mp4_6min_autofps",
                str,
            )
        )

        jobs = str(self._settings_store.value("parallel_jobs", "4", str))
        jobs_index = self.jobs_combo.findText(jobs)
        self.jobs_combo.setCurrentIndex(max(jobs_index, 0))

        self.tolerance_spin.setValue(
            self._settings_store.value("tolerance_seconds", 0.10, float)
        )
        self.create_log_checkbox.setChecked(
            self._settings_store.value("create_log", True, bool)
        )

        policy = self._settings_store.value(
            "existing_output_policy",
            ExistingOutputPolicy.SKIP.value,
            str,
        )
        buttons = {
            ExistingOutputPolicy.SKIP.value: self.skip_radio,
            ExistingOutputPolicy.OVERWRITE.value: self.overwrite_radio,
            ExistingOutputPolicy.STOP.value: self.stop_radio,
        }
        buttons.get(policy, self.skip_radio).setChecked(True)

    def _save_and_accept(self) -> None:
        values = self.conversion_settings()

        if not values.output_subfolder:
            QMessageBox.warning(
                self,
                "Invalid setting",
                "Output subfolder is required.",
            )
            return

        if values.output_subfolder in {".", ".."}:
            QMessageBox.warning(
                self,
                "Invalid setting",
                "Output subfolder cannot be . or ..",
            )
            return

        if "/" in values.output_subfolder or "\\" in values.output_subfolder:
            QMessageBox.warning(
                self,
                "Invalid setting",
                "Output subfolder must be a single folder name.",
            )
            return

        self._settings_store.setValue(
            "target_seconds",
            values.target_seconds,
        )
        self._settings_store.setValue(
            "output_subfolder",
            values.output_subfolder,
        )
        self._settings_store.setValue(
            "parallel_jobs",
            values.parallel_jobs,
        )
        self._settings_store.setValue(
            "tolerance_seconds",
            values.tolerance_seconds,
        )
        self._settings_store.setValue(
            "existing_output_policy",
            values.existing_policy.value,
        )
        self._settings_store.setValue(
            "create_log",
            values.create_log,
        )
        self.accept()


# [H264APP_P0002] end
