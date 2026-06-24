# H264 6-Minute MP4 v0.1.0

Initial source release.

## Included

- Compact near-square PySide6 window.
- Folder drag-and-drop and click-to-select workflow.
- Settings dialog available from the gear icon.
- Direct-folder `.h264` / `.264` discovery.
- Frame counting with `ffprobe`.
- Automatic frame-rate assignment using:

  `frame_count / target_duration_seconds`

- MP4 remuxing with `ffmpeg -c:v copy`.
- No image re-encoding.
- Temporary output validation before final rename.
- TSV conversion log.

## Requirements

- Python 3.10+
- PySide6
- FFmpeg with `ffmpeg` and `ffprobe` available on PATH.

## Known scope limits

- This release is source-based and does not include a macOS `.app`,
  AppImage, or packaged installer.
- Only files directly inside the selected folder are processed.
- Target-duration normalization does not reconstruct frames that were lost during recording.
