# YouTube → SWF Converter

A simple Python tool that:

1.  Downloads a YouTube video as an **MP4** using
    [yt-dlp](https://github.com/yt-dlp/yt-dlp).\
2.  Converts it to a legacy **Flash `.swf`** file using
    [ffmpeg](https://ffmpeg.org/).\
3.  Provides a **live progress bar** during conversion.\
4.  Auto-installs Python dependencies and (on Windows) downloads a
    portable ffmpeg binary if missing.

⚠️ **Note**: Flash/SWF is obsolete. This project is intended for legacy
workflows, archival, or educational purposes only. Use responsibly and
only on content you own or are licensed to download.

------------------------------------------------------------------------

## Features

-   ✅ Interactive URL prompt at runtime\
-   ✅ Auto-installs Python dependencies (`yt-dlp`, `ffmpeg-python`)\
-   ✅ Auto-downloads **portable ffmpeg** on Windows if not installed\
-   ✅ Shows conversion progress with ETA\
-   ✅ Options for output directory, framerate, quality, and whether to
    keep the intermediate MP4

------------------------------------------------------------------------

## Requirements

-   **Python 3.8+**
-   **ffmpeg**
    -   Windows: automatically downloaded if not installed\
    -   macOS/Linux: install via package manager (`brew install ffmpeg`,
        `sudo apt install ffmpeg`, etc.)

------------------------------------------------------------------------

## Installation

Clone this repo:

``` bash
git clone https://github.com/YOURNAME/youtube-to-swf.git
cd youtube-to-swf
```

Install dependencies (or let the script handle it on first run):

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

## Usage

Run the script:

``` bash
python ytdl_to_swf.py
```

You'll be prompted:

    Enter YouTube URL:

### Options

  -------------------------------------------------------------------------
  Flag            Default    Description
  --------------- ---------- ----------------------------------------------
  `-o DIR`        `output`   Output directory

  `--basename`    (title)    Base name for output SWF (no extension)

  `--framerate`   `30`       Output SWF framerate

  `--quality`     `5`        FLV video quality (1=best, 31=worst)

  `--keep-mp4`    off        Keep the intermediate MP4 instead of deleting
  -------------------------------------------------------------------------

Example:

``` bash
python ytdl_to_swf.py -o converted --basename demo_clip --framerate 24 --quality 6 --keep-mp4
```

------------------------------------------------------------------------

## Technical Details

-   **Download step**:\
    Uses `yt-dlp` to fetch the best available MP4 (merging video/audio
    if needed).\
-   **Conversion step**:\
    Invokes `ffmpeg` with:
    -   `-c:v flv` → Flash-compatible video codec\
    -   `-c:a libmp3lame` → MP3 audio for compatibility\
    -   `-q:v` quality scaling (1--31)\
    -   `-r` for custom framerate\
-   **Progress bar**:\
    ffmpeg is launched with `-progress pipe:1`, output is parsed in real
    time, and a text-based progress bar with ETA is displayed.\
-   **ffmpeg bootstrap**:\
    On Windows, if `ffmpeg.exe` is missing, the script auto-downloads a
    portable static build (from
    [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)) and places it in
    `./vendor/ffmpeg`.

------------------------------------------------------------------------

## Disclaimer

This tool is provided **as-is**.\
Downloading and converting YouTube content may violate YouTube's [Terms
of Service](https://www.youtube.com/static?gl=US&template=terms).\
Only use this tool with videos you own or are licensed to download.

------------------------------------------------------------------------
