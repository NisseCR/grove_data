"""
Entry point for the asset pipeline CLI.

Usage:
    python main.py kebab      -- rename files/folders to kebab-case
    python main.py preprocess -- convert raw assets to CDN-ready formats
    python main.py sync       -- sync output directory to Cloudflare R2 via rclone
"""

import argparse
import os
from pathlib import Path

from lib.cache import load_cache, save_cache
from lib.kebab import rename_tree
from lib.logger import setup as setup_logging
from lib.preprocess import CACHE_FILENAME
from lib.preprocess import run as run_preprocess
from lib.sync import run as run_sync


def cmd_kebab(args: argparse.Namespace) -> None:
    """Rename all files and folders under the given path to kebab-case."""
    root = Path(args.path)
    if not root.is_dir():
        print(f"Error: {root} is not a directory.")
        raise SystemExit(1)
    rename_tree(root, dry_run=args.dry_run)


def cmd_preprocess(args: argparse.Namespace) -> None:
    """Process raw assets and write converted files to OUTPUT_PATH."""
    source = Path(args.path)
    if not source.is_dir():
        print(f"Error: {source} is not a directory.")
        raise SystemExit(1)
    run_preprocess(source)


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync OUTPUT_PATH to Cloudflare R2 via rclone --checksum."""
    run_sync(dry_run=args.dry_run)


def cmd_cache(args: argparse.Namespace) -> None:
    """Remove entries from the cache that match the given prefix."""
    output_root = os.getenv("OUTPUT_PATH")
    if not output_root:
        print("Error: OUTPUT_PATH is not set in .env")
        raise SystemExit(1)
    cache_path = Path(output_root) / CACHE_FILENAME
    cache = load_cache(cache_path)

    prefix = args.prefix.replace("\\", "/").rstrip("/") + "/"
    matches = [k for k in cache if k.startswith(prefix) or k == args.prefix]

    if not matches:
        print(f"No cache entries found matching '{args.prefix}'.")
        return

    for key in matches:
        print(f"  remove {key}")

    if args.dry_run:
        print(f"\n{len(matches)} entries would be removed (dry run).")
        return

    for key in matches:
        del cache[key]
    save_cache(cache_path, cache)
    print(f"\nRemoved {len(matches)} entries from cache.")


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate subcommand."""
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Asset pipeline: rename, preprocess, and sync to R2.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    kebab_parser = subparsers.add_parser("kebab", help="Rename files and folders to kebab-case")
    kebab_parser.add_argument("path", nargs="?", default="../source", help="Directory to rename recursively (default: ../source)")
    kebab_parser.add_argument("--dry-run", action="store_true", help="Preview renames without writing")

    preprocess_parser = subparsers.add_parser("preprocess", help="Convert raw assets to CDN-ready formats")
    preprocess_parser.add_argument("path", nargs="?", default="../source", help="Source directory to preprocess (default: ../source)")

    sync_parser = subparsers.add_parser("sync", help="Sync output directory to Cloudflare R2")
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview sync without transferring files")

    cache_parser = subparsers.add_parser("cache", help="Manage the preprocess cache")
    cache_parser.add_argument("prefix", help="Path prefix to remove (e.g. playlists/ or playlists/02-mood)")
    cache_parser.add_argument("--dry-run", action="store_true", help="Preview removals without modifying the cache")

    args = parser.parse_args()

    setup_logging()

    dispatch = {
        "kebab": cmd_kebab,
        "preprocess": cmd_preprocess,
        "sync": cmd_sync,
        "cache": cmd_cache,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
