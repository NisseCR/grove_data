"""
Preprocess orchestrator.

Walks the source tree, hashes each file, skips cached entries, and dispatches
to the appropriate processor (audio, image, video). Outputs are written to a
mirrored directory tree under OUTPUT_PATH.
"""

import logging
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from lib.cache import hash_file, is_cached, load_cache, save_cache
from lib.preprocess.audio import process_audio
from lib.preprocess.image import process_image
from lib.preprocess.story import process_story
from lib.preprocess.video import process_video

load_dotenv()

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".webm", ".mp4", ".mov"}
JSON_EXTENSIONS = {".json"}
MARKDOWN_EXTENSIONS = {".md"}

CACHE_FILENAME = "cache.json"


def _output_root() -> Path:
    """Return OUTPUT_PATH from environment, raising if unset."""
    raw = os.getenv("OUTPUT_PATH")
    if not raw:
        raise RuntimeError("OUTPUT_PATH is not set in .env")
    return Path(raw)


def _mirror_path(source_root: Path, source_file: Path, output_root: Path, new_suffix: str) -> Path:
    """Return the output path for a source file, replacing its suffix."""
    relative = source_file.relative_to(source_root)
    return output_root / relative.with_suffix(new_suffix)


def run(source_root: Path) -> None:
    """
    Process all assets under source_root and write converted files to OUTPUT_PATH.

    Skips files whose SHA256 hash matches the cache. Updates the cache after
    each successful conversion.
    """
    source_root = source_root.resolve()
    output_root = _output_root()
    cache_path = output_root / CACHE_FILENAME
    cache = load_cache(cache_path)

    processed = skipped = errors = 0

    for source_file in sorted(source_root.rglob("*")):
        if not source_file.is_file():
            continue

        # Skip hidden files (e.g. .gitkeep)
        if any(part.startswith(".") for part in source_file.parts):
            continue

        suffix = source_file.suffix.lower()
        cache_key = source_file.relative_to(source_root).as_posix()
        file_hash = hash_file(source_file)

        if is_cached(cache, cache_key, file_hash):
            logger.debug("SKIP (cached): %s", cache_key)
            skipped += 1
            continue

        try:
            if suffix in AUDIO_EXTENSIONS:
                out_path = _mirror_path(source_root, source_file, output_root, ".webm")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                process_audio(source_file, out_path)

            elif suffix in IMAGE_EXTENSIONS:
                out_path = _mirror_path(source_root, source_file, output_root, ".webp")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                process_image(source_file, out_path, thumbnail=True)

            elif suffix in VIDEO_EXTENSIONS:
                out_path = _mirror_path(source_root, source_file, output_root, ".webm")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                process_video(source_file, out_path)

            elif suffix in JSON_EXTENSIONS:
                out_path = _mirror_path(source_root, source_file, output_root, ".json")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, out_path)

            elif suffix in MARKDOWN_EXTENSIONS:
                if "stories" in source_file.parts:
                    out_path = _mirror_path(source_root, source_file, output_root, ".json")
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    process_story(source_file, out_path)
                else:
                    out_path = _mirror_path(source_root, source_file, output_root, ".md")
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, out_path)

            else:
                logger.warning("SKIP (unsupported): %s", cache_key)
                continue

        except Exception as exc:
            logger.error("ERROR: %s — %s", cache_key, exc)
            errors += 1
            continue

        cache[cache_key] = file_hash
        save_cache(cache_path, cache)
        logger.info("OK: %s  →  %s", cache_key, out_path.relative_to(output_root).as_posix())
        processed += 1

    logger.info("Done — %d processed, %d cached, %d error(s).", processed, skipped, errors)
