"""SHA256 hash cache for skipping already-preprocessed files."""

import hashlib
import json
from pathlib import Path

Cache = dict[str, str]  # relative file path → sha256 hex digest


def hash_file(path: Path) -> str:
    """Return the SHA256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cache(cache_path: Path) -> Cache:
    """Load the cache from a JSON file, returning an empty dict if missing or corrupt."""
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache_path: Path, cache: Cache) -> None:
    """Write the cache dict to a JSON file, creating parent directories if needed."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def is_cached(cache: Cache, key: str, file_hash: str) -> bool:
    """Return True if key exists in the cache with a matching hash."""
    return cache.get(key) == file_hash
