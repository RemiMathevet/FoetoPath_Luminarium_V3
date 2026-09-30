"""
FoetoPath structured logging configuration.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(level=logging.INFO):
    """Configure structured logging for FoetoPath.

    Outputs to stderr (dev) + rotating file (production).
    File rotation: 5 MB max, 3 backups.
    """
    fmt = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    root = logging.getLogger()
    root.setLevel(level)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(stderr_handler)

    log_dir = Path(os.environ.get("FOETOPATH_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "foetopath.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    logging.getLogger('PIL').setLevel(logging.WARNING)
