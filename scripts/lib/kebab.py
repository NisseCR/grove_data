"""Rename files and folders under a directory tree to kebab-case."""

import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)


def to_kebab(name: str) -> str:
    """
    Convert a string to kebab-case.

    Steps: strip accents, split CamelCase, lowercase, replace separators,
    strip non-alphanumeric, collapse hyphens, trim edges.
    """
    # Decompose accented characters and drop combining marks (é → e)
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")

    # Insert hyphen between camelCase boundaries (e.g. MyFile → My-File)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)

    name = name.lower()

    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)

    # Strip characters that are not alphanumeric or hyphens
    name = re.sub(r"[^a-z0-9\-]", "", name)

    # Collapse consecutive hyphens
    name = re.sub(r"-{2,}", "-", name)

    return name.strip("-")


def _kebab_filename(path: Path) -> str:
    """Return the kebab-case name for a file, preserving its suffix."""
    if path.is_dir():
        return to_kebab(path.name)
    stem = to_kebab(path.stem)
    suffix = path.suffix.lower()
    return f"{stem}{suffix}" if stem else path.name


def rename_tree(root: Path, dry_run: bool = False) -> None:
    """
    Rename all files and folders under root to kebab-case.

    Processes deepest paths first so parent directories are renamed after
    their contents, keeping paths valid throughout. Hidden files (dot-files)
    are skipped. Collisions are reported and skipped without overwriting.
    """
    all_paths = sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True)

    renamed: list[tuple[Path, Path]] = []
    skipped_unchanged: int = 0
    collisions: list[tuple[Path, Path]] = []

    for path in all_paths:
        if not path.exists():
            continue

        # Skip hidden files (.gitkeep) and reserved folders (_shared)
        if path.name.startswith(".") or path.name.startswith("_"):
            continue

        new_name = _kebab_filename(path)

        if new_name == path.name:
            skipped_unchanged += 1
            continue

        new_path = path.parent / new_name

        # On case-insensitive filesystems (Windows/macOS), new_path.exists() is True
        # for a case-only rename because the OS sees the same file. Only treat it
        # as a collision when the target is a genuinely different file.
        is_case_only_rename = new_name.lower() == path.name.lower()
        if new_path.exists() and not is_case_only_rename:
            collisions.append((path, new_path))
            continue

        renamed.append((path, new_path))

        if not dry_run:
            path.rename(new_path)

    prefix = "[dry-run] " if dry_run else ""

    for old, new in renamed:
        logger.info("%s%s  →  %s", prefix, old.name, new.name)

    for old, new in collisions:
        logger.warning("SKIP (collision): %s  →  %s  (target already exists)", old.name, new.name)

    action = "Would rename" if dry_run else "Renamed"
    logger.info("%s %d item(s), %d already kebab-case, %d collision(s) skipped.",
                action, len(renamed), skipped_unchanged, len(collisions))
