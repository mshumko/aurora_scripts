import warnings
import pathlib
import argparse
import sys
import shutil

import ffmpeg
from PIL import Image, ImageDraw, ImageFont, ExifTags
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description=(
            "Process a path with optional start/end filenames. Example: "
            "python animate_jpg_images.py /mnt/d/photos/2025_ak_sundae_storm/ -s DSC05532 -e DSC05532"
        ))
    parser.add_argument("path", type=pathlib.Path, help="Path to a directory or file")
    parser.add_argument("--start", "-s", metavar="START", help="Start filename (optional)")
    parser.add_argument("--end", "-e", metavar="END", help="End filename (optional)")
    parser.add_argument("--extension", type=str, default='jpg', help="End filename (optional)")
    parser.add_argument("--framerate", type=int, default=24, help="Output framerate (default: 24)")
    parser.add_argument("--watermark", type=str, default="Mike Shumko", help="Watermark text to place in bottom-right (default: 'Mike Shumko')")
    parser.add_argument("--no_time", action="store_true", help="Do not include image timestamps")
    parser.add_argument("--timezone", type=str, default="AKST",)
    parser.set_defaults(time=True)
    return parser.parse_args()

def create_animation(input_files, fps=30, watermark="Mike Shumko", no_time=False, timezone="AKST"):
    ext = input_files[0].suffix.lower()

    # create temporary dir and copy files into image%04d.<ext>
    tmpdir = input_files[0].parent / "temp_imgseq"
    if tmpdir.exists():
        shutil.rmtree(tmpdir)
    tmpdir.mkdir()
    tmpdir_path = pathlib.Path(tmpdir)

    # prepare font (fallback to default)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 100)
    except Exception:
        font = ImageFont.load_default()

    margin = 100
    for i, file in enumerate(input_files, start=1):
        dest_name = f"image{i:04d}{ext}"
        dest = tmpdir_path / dest_name

        # Open with PIL, apply watermark, and save to destination
        try:
            with Image.open(file) as im:
                # ensure RGBA for alpha composite
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA")
                else:
                    im = im.convert("RGBA")

                txt = Image.new("RGBA", im.size, (255,255,255,0))
                draw = ImageDraw.Draw(txt)

                # optionally draw timestamp in lower-left
                if not no_time:
                    # try EXIF DateTimeOriginal / DateTime / DateTimeDigitized first
                    timestamp_text = None
                    try:
                        exif = im.getexif()
                        if exif:
                            for tag, val in exif.items():
                                name = ExifTags.TAGS.get(tag, tag)
                                if name in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                                    if isinstance(val, bytes):
                                        try:
                                            val = val.decode(errors='ignore')
                                        except Exception:
                                            val = str(val)
                                    timestamp_text = str(val)
                                    break
                    except Exception:
                        timestamp_text = None

                    if timestamp_text:
                        # EXIF date format is often YYYY:MM:DD HH:MM:SS -> convert to YYYY-MM-DD
                        try:
                            parts = timestamp_text.split(' ')
                            if len(parts) >= 1:
                                date_part = parts[0].replace(':', '-', 2)
                                time_part = parts[1] if len(parts) > 1 else ''
                                timestamp_text = f"{date_part} {time_part}".strip()
                        except Exception:
                            pass
                    else:
                        # fall back to file modification time
                        try:
                            ts = datetime.fromtimestamp(file.stat().st_mtime)
                            timestamp_text = ts.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            timestamp_text = ""

                    if timestamp_text:
                        if timezone:
                            timestamp_text += f" {timezone}"
                        try:
                            try:
                                bbox_ts = draw.textbbox((0, 0), timestamp_text, font=font)
                                ts_w = bbox_ts[2] - bbox_ts[0]
                                ts_h = bbox_ts[3] - bbox_ts[1]
                            except AttributeError:
                                ts_w, ts_h = draw.textsize(timestamp_text, font=font)

                            small_margin = 50
                            tx = small_margin
                            ty = im.height - ts_h - small_margin
                            # shadow then text for readability
                            draw.text((tx+1, ty+1), timestamp_text, font=font, fill=(0,0,0,180))
                            draw.text((tx, ty), timestamp_text, font=font, fill=(255,255,255,220))
                        except Exception:
                            # ignore timestamp drawing errors
                            pass

                text = watermark
                # Compute text size robustly: prefer textbbox, fall back to textsize or font.getsize
                try:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                except AttributeError:
                    try:
                        text_w, text_h = draw.textsize(text, font=font)
                    except Exception:
                        text_w, text_h = font.getsize(text)

                x = im.width - text_w - margin
                y = im.height - text_h - margin

                # draw shadow for contrast
                draw.text((x+1, y+1), text, font=font, fill=(0,0,0,180))
                draw.text((x, y), text, font=font, fill=(255,255,255,200))

                watermarked = Image.alpha_composite(im, txt)

                # Save as JPEG (or original extension); use RGB for JPEG
                if ext.lower() in (".jpg", ".jpeg"):
                    watermarked = watermarked.convert("RGB")
                    watermarked.save(dest, quality=95)
                else:
                    watermarked.save(dest)
        except Exception as err:
            # fallback to pathlib.Path.copy (Python 3.14+). If unavailable, fall back to shutil.copy2
            warnings.warn(f"failed to watermark {file}, copying without watermark.\n{err}", RuntimeWarning)
            try:
                # use the new pathlib.Path.copy API when running on Python 3.14+
                file.copy(dest)
            except AttributeError:
                # older Pythons: fall back to shutil.copy2 for metadata-preserving copy
                shutil.copy2(file, dest)

    # print temp dir contents for debugging (confirm contiguous numbering)
    names = sorted(p.name for p in tmpdir_path.iterdir())
    print("Temporary files:", names)

    # build ffmpeg input pattern (use same extension)
    pattern = str(tmpdir_path / f"image%04d{ext}")
    out_path = input_files[0].parent / f"ffmpeg_animation_{fps}fps.mp4"

    print(f"Running ffmpeg to write {out_path} from pattern {pattern} (framerate={fps})")
    try:
        inp = ffmpeg.input(pattern, framerate=fps, start_number=1)
        filter = inp.filter('scale', 1280, -1)
        filter = filter.filter('pad', 'ceil(iw/2)*2', 'ceil(ih/2)*2')
        v = filter.output(str(out_path), vcodec="libx264", pix_fmt="yuv420p")
        ffmpeg.overwrite_output(v).run(quiet=False)
    except ffmpeg.Error as e:
        print("ffmpeg failed:", e, file=sys.stderr)
        raise

    print(f"Animation written to: {out_path}")


def main():
    args = parse_args()
    path = args.path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_dir():
        if args.start and not (path / args.start).exists():
            FileNotFoundError(f"start file not found in directory: {args.start}")
        if args.end and not (path / args.end).exists():
            FileNotFoundError(f"end file not found in directory: {args.end}")
    else:
        # path is a single file; start/end are not applicable
        if args.start or args.end:
            warnings.warn("start/end ignored for single file path")

    files = sorted(path.glob(f"*.{args.extension}", case_sensitive=False))
    if len(files) == 0:
        raise FileNotFoundError(f"No files with extension {args.extension} found in {path}")
    if args.start is not None:
        files = [f for f in files if (f.name >= args.start) and (f.name <= args.end)]
    if len(files)==0:
        raise FileNotFoundError("No files remain after applying start/end filters")

    create_animation(files, fps=args.framerate, watermark=args.watermark, no_time=args.no_time, timezone=args.timezone)
    

if __name__ == "__main__":
    main()
