"""
Image preprocessing.

Converts images to WebP, caps the longest edge to 1920px, and optionally
generates a thumbnail variant (cover.thumb.webp) alongside the output file.
Requires Pillow.
"""

from pathlib import Path

from PIL import Image

MAX_DIMENSION = 1920
THUMBNAIL_DIMENSION = 400
WEBP_QUALITY = 85


def _resize(image: Image.Image, max_side: int) -> Image.Image:
    """Resize so the longest edge does not exceed max_side. Preserves aspect ratio."""
    w, h = image.size
    longest = max(w, h)
    if longest <= max_side:
        return image
    scale = max_side / longest
    return image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def process_image(source: Path, dest: Path, thumbnail: bool = False) -> None:
    """
    Convert a source image to WebP and write it to dest.

    If thumbnail is True, also writes a thumbnail variant at
    dest.stem + ".thumb.webp" in the same directory (used for cover images).
    """
    image = Image.open(source).convert("RGB")

    full_res = _resize(image, MAX_DIMENSION)
    full_res.save(dest, "WEBP", quality=WEBP_QUALITY)

    if thumbnail:
        thumb = _resize(image, THUMBNAIL_DIMENSION)
        thumb_path = dest.with_name(dest.stem + ".thumb.webp")
        thumb.save(thumb_path, "WEBP", quality=WEBP_QUALITY)
