from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .conversion_controller import ConversionController
from .settings_dialog import SettingsDialog


# [H264APP_P0003] begin


class DropFolderWidget(QFrame):
    folder_selected = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("dropFolderWidget")

        self._title_label = QLabel("Drop video folder")
        self._subtitle_label = QLabel("or click to choose")

        for label in (self._title_label, self._subtitle_label):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addStretch(1)
        layout.addWidget(self._title_label)
        layout.addSpacing(6)
        layout.addWidget(self._subtitle_label)
        layout.addStretch(1)

    def set_message(self, title: str, subtitle: str = "") -> None:
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            event.ignore()
            return

        candidate = Path(urls[0].toLocalFile())
        if candidate.is_dir():
            event.acceptProposedAction()
            return

        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            event.ignore()
            return

        candidate = Path(urls[0].toLocalFile())
        if not candidate.is_dir():
            event.ignore()
            return

        self.folder_selected.emit(candidate)
        event.acceptProposedAction()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.isEnabled()
        ):
            selected = QFileDialog.getExistingDirectory(
                self,
                "Select folder containing .h264/.264 files",
            )
            if selected:
                self.folder_selected.emit(Path(selected))
            event.accept()
            return

        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("H.264 → MP4")
        self.resize(360, 360)
        self.setMinimumSize(340, 340)
        self.setMaximumSize(420, 420)

        self._controller = ConversionController()
        self._controller.progress_changed.connect(self._on_progress_changed)
        self._controller.status_changed.connect(self._on_status_changed)
        self._controller.finished.connect(self._on_finished)
        self._controller.fatal_error.connect(self._on_fatal_error)

        central = QWidget(self)
        self.setCentralWidget(central)

        self._settings_button = QPushButton("⚙")
        self._settings_button.setToolTip("Conversion settings")
        self._settings_button.setFixedSize(28, 28)
        self._settings_button.clicked.connect(self._open_settings)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addStretch(1)
        header_layout.addWidget(self._settings_button)

        self._drop_widget = DropFolderWidget()
        self._drop_widget.folder_selected.connect(self._handle_folder_selected)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 12, 16, 16)
        root_layout.setSpacing(8)
        root_layout.addLayout(header_layout)
        root_layout.addWidget(self._drop_widget, stretch=1)
        root_layout.addSpacing(4)
        root_layout.addWidget(self._status_label)
        root_layout.addWidget(self._progress_bar)

        self.setStyleSheet(
            """
            #dropFolderWidget {
                border: 1px dashed palette(mid);
                border-radius: 10px;
            }
            #dropFolderWidget:hover {
                border-color: palette(highlight);
            }
            """
        )

    def closeEvent(self, event) -> None:
        if not self._controller.is_running:
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Cancel conversion?",
            "Conversion is active. Cancel all running tasks and close?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self._controller.cancel()
            event.accept()
            return

        event.ignore()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()

    def _handle_folder_selected(self, folder: Path) -> None:
        if self._controller.is_running:
            return

        dialog = SettingsDialog(self)
        settings = dialog.conversion_settings()

        self._drop_widget.setEnabled(False)
        self._settings_button.setEnabled(False)
        self._drop_widget.set_message("Converting", "Preparing files…")
        self._status_label.setText("0 / 0 completed · 0 failed")
        self._progress_bar.setRange(0, 0)

        self._controller.start(folder, settings)

    def _on_progress_changed(
        self,
        done: int,
        total: int,
        completed: int,
        failed: int,
        skipped: int,
    ) -> None:
        self._progress_bar.setRange(0, max(total, 1))
        self._progress_bar.setValue(done)
        self._status_label.setText(
            f"{done} / {total} completed · {failed} failed"
        )

    def _on_status_changed(self, message: str) -> None:
        self._drop_widget.set_message("Converting", message)

    def _on_finished(
        self,
        completed: int,
        failed: int,
        skipped: int,
        output_dir: Path,
    ) -> None:
        self._drop_widget.setEnabled(True)
        self._settings_button.setEnabled(True)

        if failed:
            self._drop_widget.set_message(
                "Completed with errors",
                f"{completed} converted · {failed} failed · {skipped} skipped",
            )
        else:
            self._drop_widget.set_message(
                "Completed",
                f"{completed} converted · {skipped} skipped",
            )

    def _on_fatal_error(self, message: str) -> None:
        self._drop_widget.setEnabled(True)
        self._settings_button.setEnabled(True)
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._drop_widget.set_message("Cannot start", message)
        QMessageBox.warning(self, "Conversion error", message)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    application = QApplication(sys.argv)
    application.setApplicationName("H264 6-Minute MP4")

    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())


# [H264APP_P0003] end
