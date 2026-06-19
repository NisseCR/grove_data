"""
Entry point for the asset pipeline CLI.

Usage:
    python main.py kebab      -- rename files/folders to kebab-case
    python main.py preprocess -- convert raw assets to CDN-ready formats
    python main.py sync       -- sync output directory to Cloudflare R2 via rclone
"""

import argparse
from pathlib import Path

from lib.kebab import rename_tree
from lib.logger import setup as setup_logging
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

    args = parser.parse_args()

    setup_logging()

    dispatch = {
        "kebab": cmd_kebab,
        "preprocess": cmd_preprocess,
        "sync": cmd_sync,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
