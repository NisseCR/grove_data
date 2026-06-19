# Asset Pipeline

Local data pipeline for *At the Grove of the Well*. Converts raw source assets to web-ready formats and syncs them to Cloudflare R2.

## Pipeline

```
source/  →  kebab  →  preprocess  →  sync  →  R2 bucket
```

| Step | What it does |
|---|---|
| `kebab` | Renames all files and folders to kebab-case |
| `preprocess` | Converts assets to web-ready formats (see below) |
| `sync` | Uploads changed files to Cloudflare R2, deletes removed files |

**Output formats**

| Input | Output |
|---|---|
| Audio (`.mp3`, `.wav`, `.flac`, `.ogg`, etc.) | `.webm` (Opus, 128kbps, loudness-normalised to −16 LUFS, 48 kHz) |
| Images (`.jpg`, `.png`, etc.) | `.webp` + `.thumb.webp` |
| Video (`.mp4`, `.mov`, etc.) | `.webm` |
| Scene configs (`.json`) | `.json` (copied as-is) |
| Story chapters (`.md`) | `.json` (parsed frontmatter + content) |

## Setup

Requires Python 3.12+, `ffmpeg` on PATH, and a `.env` file at the repo root:

```env
OUTPUT_PATH=M:\path\to\output
R2_ACCOUNT_ID=your-account-id
R2_BUCKET=your-bucket-name
R2_ACCESS_KEY=your-access-key
R2_SECRET_KEY=your-secret-key
```

Install dependencies:

```
pip install -r requirements.txt
```

## Usage

Run from the `scripts/` directory on Windows (output is a local Windows path).

```
python main.py kebab
python main.py preprocess
python main.py sync
python main.py sync --dry-run
```

A Tkinter GUI is also available via `ui.py` (or `run.bat`), exposing kebab, preprocess, and sync as buttons.

## Caching

The preprocessor writes a `cache.json` to `OUTPUT_PATH` tracking the SHA256 hash of each source file. Unchanged files are skipped on subsequent runs. Delete `cache.json` to force a full re-run.
