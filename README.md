**Aurora Image Animator**

- **Description:** Generates a video animation from a sequence of JPEG images. The tool copies images into a temporary ordered sequence, applies a watermark and optional timestamps, then encodes an MP4 using `ffmpeg`.

I am learning the uv package manager so all of the below examples use it. pip will also work.

- **Main script:** [animate_jpg_images.py](animate_jpg_images.py)

**Prerequisites:**
- **Python:** 3.8+
- **System:** `ffmpeg` must be installed and available on `PATH`.
- **Python packages:** `Pillow`, `ffmpeg-python`, `tqdm`

Install dependencies (example):

```bash
python -m uv install Pillow ffmpeg-python tqdm
```

**Usage**
- **Basic:** Provide a directory containing images (default extension `jpg`):

```bash
uv run animate_jpg_images.py /path/to/images/
```

- **Options:**
- **`path`:** Positional path to a directory (or single file). If a directory is provided the tool will collect images by extension.
- **`--start`, `-s` / `--end`, `-e`:** Optional start and end filenames to filter the sequence (inclusive). Filenames are compared lexicographically.
- **`--extension`:** Image extension to match (default: `jpg`).
- **`--framerate`:** Output framerate in frames per second (default: 24).
- **`--watermark`:** Watermark text to render in the bottom-right (default: "Mike Shumko").
- **`--no_time`:** If set, do not render image timestamps on the frames.
- **`--timezone`:** Text appended to timestamps (default: `AKST`).

- **Example - limit by filename and change framerate:**

```bash
python animate_jpg_images.py /mnt/d/photos/2025_ak_sundae_st/ -s DSC05532 -e DSC05560 --framerate 30
```

- **Example - different extension and no timestamps:**

```bash
python animate_jpg_images.py /path/to/images --extension png --no_time --watermark "My Name"
```

**Output:**
- The script writes an MP4 next to the input images named like `ffmpeg_animation_24fps.mp4`.

**How it works (brief):**
- The script copies input images into a temporary folder named `temp_imgseq` with contiguous names (`image0001.jpg`, ...), draws watermark and optional timestamps using EXIF DateTimeOriginal (falls back to file modification time), then invokes `ffmpeg` (via `ffmpeg-python`) to produce an H.264 MP4 with yuv420p pixel format.

**Notes & Troubleshooting:**
- If no images are found for the given extension the script will raise a `FileNotFoundError`.
- If you see incorrect timestamps, ensure your images contain EXIF `DateTimeOriginal` or use file mtimes.
- Temporary files are created in a `temp_imgseq` directory next to the input images; the script removes and recreates it each run.

**License & Contributing**
- See the repository `LICENSE` file for license terms. Contributions and issues are welcome.

