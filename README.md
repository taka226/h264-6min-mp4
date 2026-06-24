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

- Miniconda, Anaconda, or Mambaforge
- Python 3.10 or later
- FFmpeg, including both `ffmpeg` and `ffprobe`

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/h264-6min-mp4.git
cd h264-6min-mp4
```

Create and activate a Conda environment:

```bash
conda create -n h264-6min-mp4 python=3.11 -y
conda activate h264-6min-mp4
```

Install FFmpeg and PySide6:

```bash
conda install -c conda-forge ffmpeg pyside6 -y
python -m pip install -r requirements.txt
```

Check that both command-line tools are visible:

```bash
ffmpeg -version
ffprobe -version
```

## Run

```bash
conda activate h264-6min-mp4
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
conda activate h264-6min-mp4

python -m py_compile \
  h264_6min_mp4/conversion_controller.py \
  h264_6min_mp4/settings_dialog.py \
  h264_6min_mp4/app.py

python -c "from h264_6min_mp4.app import main; print('IMPORT PASS')"
```

## License

Add a license before distributing beyond your own laboratory.
