#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
import time
from pathlib import Path

FFMPEG_WINDOWS_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
LOCAL_FFMPEG_DIR = Path(__file__).parent / "vendor" / "ffmpeg"  # where we place a portable ffmpeg on Windows

def ensure_dependency(pkg_name, import_name=None):
    """Check if a dependency is installed, install via pip if not."""
    import importlib
    try:
        importlib.import_module(import_name or pkg_name)
    except ImportError:
        print(f"[INFO] Missing {pkg_name}, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])
        importlib.invalidate_caches()

# Ensure yt-dlp and ffmpeg-python (wrapper only; still need ffmpeg binary)
ensure_dependency("yt-dlp")
ensure_dependency("ffmpeg-python", "ffmpeg")

from yt_dlp import YoutubeDL

def _ffmpeg_in_path() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

def _prepend_to_env_path(dir_path: Path):
    os.environ["PATH"] = str(dir_path) + os.pathsep + os.environ.get("PATH", "")

def _download_with_progress(url: str, dest: Path):
    from urllib.request import urlopen, Request
    chunk = 1024 * 256
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as r, open(dest, "wb") as f:
        total = r.length or 0
        read = 0
        while True:
            data = r.read(chunk)
            if not data:
                break
            f.write(data)
            read += len(data)
            if total:
                pct = int(read * 100 / total)
                print(f"\r[ffmpeg] Downloading... {pct}%", end="", flush=True)
    print("\r[ffmpeg] Download complete.        ")

def _install_portable_ffmpeg_windows():
    """Download & unpack a portable ffmpeg into ./vendor/ffmpeg and put it on PATH (Windows only)."""
    LOCAL_FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

    # If already placed earlier, just add to PATH
    ffmpeg_exe = LOCAL_FFMPEG_DIR / "bin" / "ffmpeg.exe"
    if ffmpeg_exe.exists():
        _prepend_to_env_path(ffmpeg_exe.parent)
        return

    print("[INFO] ffmpeg not found. Downloading a portable build for Windows...")
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        zip_path = td_path / "ffmpeg.zip"
        _download_with_progress(FFMPEG_WINDOWS_ZIP_URL, zip_path)

        # Unzip
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(td_path)

        # Find the unpacked root (it contains bin/ffmpeg.exe)
        candidate_root = None
        for p in td_path.iterdir():
            if p.is_dir() and (p / "bin" / "ffmpeg.exe").exists():
                candidate_root = p
                break
        if candidate_root is None:
            raise RuntimeError("Could not locate ffmpeg.exe in the downloaded archive.")

        # Copy into LOCAL_FFMPEG_DIR
        if (LOCAL_FFMPEG_DIR).exists():
            shutil.rmtree(LOCAL_FFMPEG_DIR)
        shutil.copytree(candidate_root, LOCAL_FFMPEG_DIR)

    # Put portable ffmpeg on PATH for this process
    _prepend_to_env_path((LOCAL_FFMPEG_DIR / "bin"))

    # Verify
    if not _ffmpeg_in_path():
        raise RuntimeError("Portable ffmpeg setup failed unexpectedly.")

def check_ffmpeg():
    if _ffmpeg_in_path():
        return
    if platform.system().lower().startswith("win"):
        try:
            _install_portable_ffmpeg_windows()
            print("[INFO] Portable ffmpeg installed and added to PATH for this run.")
        except Exception as e:
            print(f"[ERROR] Could not auto-install ffmpeg: {e}")
            print("You can also install manually and add it to PATH.")
            sys.exit(1)
    else:
        print("ffmpeg not found in PATH. Please install it via your package manager (e.g., apt/brew/dnf) and try again.")
        sys.exit(1)

def download_mp4(url: str, out_dir: Path):
    """
    Download as MP4 and return (mp4_path, duration_seconds or None).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / "%(title)s-%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        "noplaylist": True,
        "quiet": False,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        base = ydl.prepare_filename(info)
        mp4_path = Path(base).with_suffix(".mp4")
        if not mp4_path.exists():
            # fallback: search by id
            vid = info.get("id", "")
            matches = list(out_dir.glob(f"*{vid}*.mp4"))
            if matches:
                mp4_path = matches[0]
            else:
                raise FileNotFoundError("MP4 not found after download.")
        duration = info.get("duration")  # seconds (int) if available
        return mp4_path, (float(duration) if duration else None)

def _ffprobe_duration_seconds(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            stderr=subprocess.DEVNULL
        )
        return float(out.strip())
    except Exception:
        return None

def _format_time(sec: float) -> str:
    if sec is None or sec < 0:
        return "--:--"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def convert_to_swf_with_progress(mp4_path: Path, swf_path: Path, duration_sec: float | None,
                                 quality: int = 5, framerate: int = 30):
    """
    Convert MP4 to SWF and render a live progress bar by parsing `-progress` output.
    If duration_sec is None, attempts ffprobe; if still unknown, shows frames processed without %.
    """
    if duration_sec is None:
        duration_sec = _ffprobe_duration_seconds(mp4_path)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(mp4_path),
        "-c:v", "flv",
        "-q:v", str(max(1, min(31, quality))),
        "-r", str(framerate),
        "-pix_fmt", "yuv420p",
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "libmp3lame",
        # progress reporting
        "-progress", "pipe:1",
        "-nostats",
        str(swf_path)
    ]

    # Start ffmpeg and read progress lines
    start_time = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)

    bar_width = 50
    last_pct = -1
    out_time_sec = 0.0

    try:
        if not proc.stdout:
            raise RuntimeError("Failed to capture ffmpeg progress output.")

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            # Parse out_time_ms or out_time
            if line.startswith("out_time_ms="):
                try:
                    out_time_ms = int(line.split("=", 1)[1])
                    out_time_sec = out_time_ms / 1_000_000.0
                except Exception:
                    pass
            elif line.startswith("out_time="):
                # Format like HH:MM:SS.micro
                try:
                    t = line.split("=", 1)[1]
                    h, m, s = t.split(":")
                    out_time_sec = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    pass
            elif line.startswith("progress=") and line.endswith("end"):
                # final update; break after printing 100%
                out_time_sec = duration_sec or out_time_sec

            # Render progress
            if duration_sec and duration_sec > 0:
                pct = max(0.0, min(1.0, out_time_sec / duration_sec))
                filled = int(pct * bar_width)
                bar = "#" * filled + "-" * (bar_width - filled)
                elapsed = time.time() - start_time
                eta = (elapsed / pct - elapsed) if pct > 0 else 0
                pct_int = int(pct * 100)
                # avoid spamming the console on every tiny change
                if pct_int != last_pct:
                    last_pct = pct_int
                    print(f"\r[SWF] |{bar}| {pct_int:3d}%  "
                          f"{_format_time(out_time_sec)} / {_format_time(duration_sec)}  "
                          f"ETA {_format_time(eta)}", end="", flush=True)
            else:
                # No duration known – just show time processed
                print(f"\r[SWF] Converting... {_format_time(out_time_sec)} elapsed", end="", flush=True)

        proc.wait()
    finally:
        # ensure a newline after the bar
        print()

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)

def main():
    parser = argparse.ArgumentParser(description="Download YouTube video as MP4 and convert to SWF.")
    parser.add_argument("-o", "--outdir", default="output", help="Output directory (default: ./output)")
    parser.add_argument("--basename", default=None, help="Base name for output SWF (no extension)")
    parser.add_argument("--framerate", type=int, default=30, help="SWF framerate")
    parser.add_argument("--quality", type=int, default=5, help="Video quality 1(best)-31(worst)")
    parser.add_argument("--keep-mp4", action="store_true", help="Keep the MP4 after SWF is created")
    args = parser.parse_args()

    # Prompt user for URL at runtime
    url = input("Enter YouTube URL: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        sys.exit(1)

    check_ffmpeg()

    out_dir = Path(args.outdir).expanduser().resolve()
    mp4_path, duration_sec = download_mp4(url, out_dir)

    swf_name = f"{args.basename}.swf" if args.basename else mp4_path.with_suffix(".swf").name
    swf_path = out_dir / swf_name

    convert_to_swf_with_progress(mp4_path, swf_path, duration_sec, args.quality, args.framerate)

    print(f"✅ Done!\nMP4: {mp4_path}\nSWF: {swf_path}")
    if not args.keep_mp4:
        try:
            mp4_path.unlink()
            print("Removed intermediate MP4 (use --keep-mp4 to retain).")
        except Exception:
            pass

if __name__ == "__main__":
    main()
