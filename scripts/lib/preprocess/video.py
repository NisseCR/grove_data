"""
Video preprocessing.

Videos are passed through without re-encoding. A WebP thumbnail is extracted
from the first frame and written alongside the output file as dest.stem + ".thumb.webp".
Requires ffmpeg on PATH and Pillow.
"""

import io
import logging
import shutil
import subprocess
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

THUMB_WIDTH = 480
WEBP_QUALITY = 82


def _extract_thumbnail(source: Path) -> bytes | None:
    """Extract the first frame of a video and return it as WebP bytes, or None on failure."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-i", str(source),
            "-ss", "0",
            "-vframes", "1",
            "-vf", f"scale={THUMB_WIDTH}:-2",
            "-f", "image2pipe",
            "-vcodec", "png",
            "pipe:1",
        ],
        capture_output=True,
    )
    if not result.stdout:
        return None
    img = Image.open(io.BytesIO(result.stdout))
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=WEBP_QUALITY)
    return buf.getvalue()


def process_video(source: Path, dest: Path) -> None:
    """
    Copy a video file to dest (passthrough, no re-encoding) and write a
    thumbnail as dest.stem + ".thumb.webp" in the same directory.

    Thumbnail failure is non-fatal — a warning is logged and processing continues.
    """
    shutil.copy2(source, dest)

    thumb_data = _extract_thumbnail(source)
    if thumb_data is None:
        logger.warning("Could not extract thumbnail for %s", source.name)
        return

    thumb_path = dest.with_name(dest.stem + ".thumb.webp")
    thumb_path.write_bytes(thumb_data)
