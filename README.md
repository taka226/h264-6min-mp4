# H.264 → 6-Minute MP4

A compact PySide6 application for converting raw `.h264` / `.264` video files
into MP4 containers without re-encoding the H.264 video stream.

The application is intended for recordings that should be normalized to a fixed
duration, defaulting to 360 seconds.

## What it does

For every `.h264` or `.264` file directly inside a selected folder:

1. Counts decoded video frames using `ffprobe`.
2. Calculates input frame rate as:

   ```text
   assigned_fps = frame_count / target_duration_seconds
   ```

3. Remuxes the raw H.264 stream into MP4 using `ffmpeg -c:v copy`.
4. Validates the resulting MP4 duration.
5. Writes outputs into a subfolder without changing the base filename.

Example:

```text
recording_001.h264
→ mp4_6min_autofps/recording_001.mp4
```

No video re-encoding is performed. Image quality is therefore unchanged.

## Supported platforms

- macOS
- Ubuntu Linux

## Requirements

- Python 3.10 or later
- FFmpeg, including both `ffmpeg` and `ffprobe`
- PySide6

### macOS

```bash
brew install ffmpeg
```

### Ubuntu

```bash
sudo apt update
sudo apt install ffmpeg
```

## Installation

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/h264-6min-mp4.git
cd h264-6min-mp4

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
python -m h264_6min_mp4.app
```

## Interface

- Drop a folder containing raw H.264 files onto the window.
- Or click the drop area to select a folder.
- Conversion starts automatically.
- Click the gear icon to configure target duration, output folder name,
  parallel jobs, handling of existing outputs, validation tolerance, and TSV log generation.

Only files directly inside the selected folder are processed. Subfolders are not scanned.

## Output

By default, converted MP4 files are written to:

```text
mp4_6min_autofps/
```

A `conversion_log.tsv` file is also created unless disabled in settings.

## Important limitation

This application normalizes each output to the target duration by assigning:

```text
fps = frame_count / target_duration
```

If a recording has fewer or more frames than expected for nominal 60 fps,
the resulting MP4 still becomes 360 seconds long, but its effective temporal
sampling rate changes. This does not recover dropped frames.

## Development validation

```bash
python -m py_compile \
  h264_6min_mp4/conversion_controller.py \
  h264_6min_mp4/settings_dialog.py \
  h264_6min_mp4/app.py

python -c "from h264_6min_mp4.app import main; print('IMPORT PASS')"
```

## License

Add a license before distributing beyond your own laboratory.
