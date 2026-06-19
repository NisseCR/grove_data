"""
Cloudflare R2 sync via boto3.

Syncs OUTPUT_PATH to R2_BUCKET using content-based comparison (MD5 vs ETag)
so changes are detected reliably across devices regardless of modification time.
Files present in R2 but removed locally are deleted from the bucket.
"""

import hashlib
import logging
import os
from pathlib import Path

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SKIP_FILES = {"cache.json"}

# Force single-part uploads so ETags are plain MD5 and our comparison works.
# Assets are never large enough to warrant multipart anyway.
TRANSFER_CONFIG = TransferConfig(multipart_threshold=500 * 1024 * 1024)


def _require_env(key: str) -> str:
    """Return an environment variable's value, raising if unset."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"{key} is not set in .env")
    return value


def _md5(path: Path) -> str:
    """Return the MD5 hex digest of a file (matches R2 ETag for single-part uploads)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    account_id = _require_env("R2_ACCOUNT_ID")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=_require_env("R2_ACCESS_KEY"),
        aws_secret_access_key=_require_env("R2_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
    )


def _list_remote(client, bucket: str) -> dict[str, str]:
    """Return a dict of {key: etag} for all objects currently in the bucket."""
    remote = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            # ETags from R2 are quoted strings — strip the quotes
            remote[obj["Key"]] = obj["ETag"].strip('"')
    return remote


def run(dry_run: bool = False) -> None:
    """
    Sync OUTPUT_PATH to R2_BUCKET.

    Uploads files that are new or whose MD5 differs from the remote ETag.
    Deletes remote objects that no longer exist locally.
    Skips files listed in SKIP_FILES (e.g. cache.json).
    Pass dry_run=True to preview all actions without writing anything.
    """
    output_path = Path(_require_env("OUTPUT_PATH"))
    bucket = _require_env("R2_BUCKET")

    if not output_path.is_dir():
        raise RuntimeError(f"OUTPUT_PATH does not exist: {output_path}")

    client = _build_client()
    remote = _list_remote(client, bucket)

    local_keys: set[str] = set()
    uploaded = skipped = deleted = errors = 0
    prefix = "[dry-run] " if dry_run else ""

    for local_file in sorted(output_path.rglob("*")):
        if not local_file.is_file():
            continue
        if local_file.name in SKIP_FILES:
            continue

        key = local_file.relative_to(output_path).as_posix()
        local_keys.add(key)
        local_md5 = _md5(local_file)

        if remote.get(key) == local_md5:
            skipped += 1
            continue

        action = "upload (new)" if key not in remote else "upload (changed)"
        logger.info("%s%s: %s", prefix, action, key)

        if not dry_run:
            try:
                client.upload_file(str(local_file), bucket, key, Config=TRANSFER_CONFIG)
            except Exception as exc:
                logger.error("ERROR uploading %s — %s", key, exc)
                errors += 1
                continue
        uploaded += 1

    for key in remote:
        if key not in local_keys:
            logger.info("%sdelete: %s", prefix, key)
            if not dry_run:
                try:
                    client.delete_object(Bucket=bucket, Key=key)
                except Exception as exc:
                    logger.error("ERROR deleting %s — %s", key, exc)
                    errors += 1
                    continue
            deleted += 1

    action = "Would transfer" if dry_run else "Transferred"
    logger.info("%s %d upload(s), %d unchanged, %d delete(s), %d error(s).",
                action, uploaded, skipped, deleted, errors)
