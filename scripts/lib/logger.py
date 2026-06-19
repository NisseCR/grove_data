"""Logging configuration for the asset pipeline."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "pipeline.log"

FILE_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
CONSOLE_FORMAT = "%(message)s"


def setup() -> None:
    """Configure root logger with a console handler and a rotating file handler."""
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))

    root.addHandler(console)
    root.addHandler(file_handler)
