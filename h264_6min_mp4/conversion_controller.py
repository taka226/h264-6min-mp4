from __future__ import annotations

import csv
import logging
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

LOGGER = logging.getLogger(__name__)

# [H264APP_P0001] begin


class ExistingOutputPolicy(str, Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    STOP = "stop"


@dataclass(frozen=True)
class ConversionSettings:
    target_seconds: int = 360
    output_subfolder: str = "mp4_6min_autofps"
    parallel_jobs: int = 4
    existing_policy: ExistingOutputPolicy = ExistingOutputPolicy.SKIP
    tolerance_seconds: float = 0.10
    create_log: bool = True


@dataclass(frozen=True)
class ConversionRecord:
    input_file: Path
    output_file: Path
    status: str
    frame_count: str = ""
    assigned_fps: str = ""
    duration_seconds: str = ""
    message: str = ""


def discover_candidates(folder: Path, output_subfolder: str) -> list[Path]:
    """Return raw H.264 files directly inside folder; never recurse."""
    output_dir = folder / output_subfolder
    candidates: list[Path] = []

    for path in folder.iterdir():
        if path == output_dir or not path.is_file():
            continue
        if path.suffix.lower() in {".h264", ".264"}:
            candidates.append(path)

    return sorted(candidates, key=lambda item: item.name.casefold())


def output_path_for(input_file: Path, output_dir: Path) -> Path:
    return output_dir / f"{input_file.stem}.mp4"


def temporary_output_path_for(output_file: Path) -> Path:
    return output_file.with_name(f".{output_file.stem}.partial.mp4")


def assigned_fps_for(frame_count: int, target_seconds: int) -> str:
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    if target_seconds <= 0:
        raise ValueError("target_seconds must be positive")

    fps = frame_count / target_seconds
    return f"{fps:.12f}".rstrip("0").rstrip(".")


def duration_is_valid(
    duration_seconds: float,
    target_seconds: int,
    tolerance_seconds: float,
) -> bool:
    return abs(duration_seconds - target_seconds) <= tolerance_seconds


class ConversionController(QObject):
    progress_changed = Signal(int, int, int, int, int)
    status_changed = Signal(str)
    finished = Signal(int, int, int, Path)
    fatal_error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._settings: ConversionSettings | None = None
        self._folder: Path | None = None
        self._output_dir: Path | None = None
        self._queue: list[Path] = []
        self._active: dict[QProcess, Path] = {}
        self._records: list[ConversionRecord] = []
        self._completed = 0
        self._failed = 0
        self._skipped = 0
        self._total = 0
        self._cancel_requested = False
        self._stop_requested = False

    @property
    def is_running(self) -> bool:
        return bool(self._active or self._queue)

    def start(self, folder: Path, settings: ConversionSettings) -> None:
        if self.is_running:
            raise RuntimeError("conversion is already running")

        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            self.fatal_error.emit(
                "ffmpeg and/or ffprobe were not found on PATH. "
                "Install ffmpeg and restart the application."
            )
            return

        candidates = discover_candidates(folder, settings.output_subfolder)
        if not candidates:
            self.fatal_error.emit("No .h264 or .264 files were found in this folder.")
            return

        self._settings = settings
        self._folder = folder
        self._output_dir = folder / settings.output_subfolder
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._queue = []
        self._active = {}
        self._records = []
        self._completed = 0
        self._failed = 0
        self._skipped = 0
        self._total = len(candidates)
        self._cancel_requested = False
        self._stop_requested = False

        for input_file in candidates:
            output_file = output_path_for(input_file, self._output_dir)

            if not output_file.exists():
                self._queue.append(input_file)
                continue

            if settings.existing_policy == ExistingOutputPolicy.SKIP:
                self._skipped += 1
                self._records.append(
                    ConversionRecord(
                        input_file=input_file,
                        output_file=output_file,
                        status="skipped",
                        message="existing output file",
                    )
                )
                continue

            if settings.existing_policy == ExistingOutputPolicy.STOP:
                self._stop_requested = True
                self._records.append(
                    ConversionRecord(
                        input_file=input_file,
                        output_file=output_file,
                        status="stopped",
                        message="existing output file",
                    )
                )
                break

            self._queue.append(input_file)

        self._emit_progress()

        if self._stop_requested:
            self.status_changed.emit("Stopped: an output MP4 already exists.")
            self._finish_if_done()
            return

        self.status_changed.emit("Preparing conversion…")
        self._schedule_next()

    def cancel(self) -> None:
        self._cancel_requested = True
        self._queue.clear()

        for process in list(self._active):
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()

        self.status_changed.emit("Cancelling…")

    def _schedule_next(self) -> None:
        settings = self._require_settings()

        while (
            not self._cancel_requested
            and not self._stop_requested
            and self._queue
            and len(self._active) < settings.parallel_jobs
        ):
            self._probe_frame_count(self._queue.pop(0))

        self._finish_if_done()

    def _probe_frame_count(self, input_file: Path) -> None:
        process = QProcess(self)
        process.setProgram("ffprobe")
        process.setArguments(
            [
                "-v",
                "error",
                "-f",
                "h264",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=nb_read_frames",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                str(input_file),
            ]
        )
        process.finished.connect(
            lambda exit_code, exit_status, p=process, source=input_file:
            self._on_probe_frame_count_finished(
                p,
                source,
                exit_code,
                exit_status,
            )
        )
        self._active[process] = input_file
        process.start()

    def _on_probe_frame_count_finished(
        self,
        process: QProcess,
        input_file: Path,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        self._active.pop(process, None)

        if self._cancel_requested:
            self._schedule_next()
            return

        output_file = output_path_for(input_file, self._require_output_dir())
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", "replace").strip()
        stderr = bytes(process.readAllStandardError()).decode("utf-8", "replace").strip()

        if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
            self._record_failure(
                input_file,
                output_file,
                f"ffprobe frame count failed: {stderr or 'unknown error'}",
            )
            self._schedule_next()
            return

        try:
            frame_count = int(stdout)
            if frame_count <= 0:
                raise ValueError
        except ValueError:
            self._record_failure(
                input_file,
                output_file,
                f"invalid frame count returned by ffprobe: {stdout!r}",
            )
            self._schedule_next()
            return

        self._remux(input_file, output_file, frame_count)

    def _remux(
        self,
        input_file: Path,
        output_file: Path,
        frame_count: int,
    ) -> None:
        settings = self._require_settings()
        temp_output = temporary_output_path_for(output_file)
        temp_output.unlink(missing_ok=True)

        process = QProcess(self)
        process.setProgram("ffmpeg")
        process.setArguments(
            [
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-r",
                assigned_fps_for(frame_count, settings.target_seconds),
                "-f",
                "h264",
                "-i",
                str(input_file),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-video_track_timescale",
                str(frame_count),
                str(temp_output),
            ]
        )
        process.finished.connect(
            lambda exit_code, exit_status, p=process, source=input_file,
            destination=output_file, frames=frame_count:
            self._on_remux_finished(
                p,
                source,
                destination,
                frames,
                exit_code,
                exit_status,
            )
        )
        self._active[process] = input_file
        process.start()

    def _on_remux_finished(
        self,
        process: QProcess,
        input_file: Path,
        output_file: Path,
        frame_count: int,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        self._active.pop(process, None)
        temp_output = temporary_output_path_for(output_file)
        stderr = bytes(process.readAllStandardError()).decode("utf-8", "replace").strip()

        if self._cancel_requested:
            temp_output.unlink(missing_ok=True)
            self._schedule_next()
            return

        if (
            exit_status != QProcess.ExitStatus.NormalExit
            or exit_code != 0
            or not temp_output.exists()
        ):
            temp_output.unlink(missing_ok=True)
            self._record_failure(
                input_file,
                output_file,
                f"ffmpeg remux failed: {stderr or 'unknown error'}",
            )
            self._schedule_next()
            return

        self._probe_duration(input_file, output_file, frame_count)

    def _probe_duration(
        self,
        input_file: Path,
        output_file: Path,
        frame_count: int,
    ) -> None:
        temp_output = temporary_output_path_for(output_file)

        process = QProcess(self)
        process.setProgram("ffprobe")
        process.setArguments(
            [
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                str(temp_output),
            ]
        )
        process.finished.connect(
            lambda exit_code, exit_status, p=process, source=input_file,
            destination=output_file, frames=frame_count:
            self._on_probe_duration_finished(
                p,
                source,
                destination,
                frames,
                exit_code,
                exit_status,
            )
        )
        self._active[process] = input_file
        process.start()

    def _on_probe_duration_finished(
        self,
        process: QProcess,
        input_file: Path,
        output_file: Path,
        frame_count: int,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        self._active.pop(process, None)

        settings = self._require_settings()
        temp_output = temporary_output_path_for(output_file)
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", "replace").strip()
        stderr = bytes(process.readAllStandardError()).decode("utf-8", "replace").strip()

        try:
            duration = float(stdout)
        except ValueError:
            duration = -1.0

        if (
            exit_status != QProcess.ExitStatus.NormalExit
            or exit_code != 0
            or not duration_is_valid(
                duration,
                settings.target_seconds,
                settings.tolerance_seconds,
            )
        ):
            temp_output.unlink(missing_ok=True)
            self._record_failure(
                input_file,
                output_file,
                "duration validation failed: "
                f"duration={stdout!r}, target={settings.target_seconds}, "
                f"ffprobe={stderr or 'no ffprobe error text'}",
            )
            self._schedule_next()
            return

        if output_file.exists():
            if settings.existing_policy != ExistingOutputPolicy.OVERWRITE:
                temp_output.unlink(missing_ok=True)
                self._record_failure(
                    input_file,
                    output_file,
                    "output appeared during conversion; refusing overwrite",
                )
                self._schedule_next()
                return
            output_file.unlink()

        temp_output.replace(output_file)

        expected_frame_count = settings.target_seconds * 60
        warning = ""
        if abs(frame_count - expected_frame_count) > 1:
            warning = (
                "frame count differs from nominal 60-fps expectation "
                f"({expected_frame_count})"
            )

        self._completed += 1
        self._records.append(
            ConversionRecord(
                input_file=input_file,
                output_file=output_file,
                status="ok",
                frame_count=str(frame_count),
                assigned_fps=assigned_fps_for(frame_count, settings.target_seconds),
                duration_seconds=f"{duration:.6f}",
                message=warning,
            )
        )
        self._emit_progress()
        self._schedule_next()

    def _record_failure(
        self,
        input_file: Path,
        output_file: Path,
        message: str,
    ) -> None:
        LOGGER.warning("Conversion failed for %s: %s", input_file, message)
        self._failed += 1
        self._records.append(
            ConversionRecord(
                input_file=input_file,
                output_file=output_file,
                status="failed",
                message=message,
            )
        )
        self._emit_progress()

    def _emit_progress(self) -> None:
        done = self._completed + self._failed + self._skipped
        self.progress_changed.emit(
            done,
            self._total,
            self._completed,
            self._failed,
            self._skipped,
        )

    def _finish_if_done(self) -> None:
        if self._active or self._queue:
            return

        if self._output_dir is None or self._settings is None:
            return

        if self._settings.create_log:
            self._write_log(self._output_dir / "conversion_log.tsv")

        self.finished.emit(
            self._completed,
            self._failed,
            self._skipped,
            self._output_dir,
        )

    def _write_log(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(
                [
                    "input_file",
                    "output_file",
                    "status",
                    "frame_count",
                    "assigned_fps",
                    "duration_seconds",
                    "message",
                ]
            )
            for record in self._records:
                writer.writerow(
                    [
                        str(record.input_file),
                        str(record.output_file),
                        record.status,
                        record.frame_count,
                        record.assigned_fps,
                        record.duration_seconds,
                        record.message,
                    ]
                )

    def _require_settings(self) -> ConversionSettings:
        if self._settings is None:
            raise RuntimeError("conversion settings are unavailable")
        return self._settings

    def _require_output_dir(self) -> Path:
        if self._output_dir is None:
            raise RuntimeError("output directory is unavailable")
        return self._output_dir


# [H264APP_P0001] end
