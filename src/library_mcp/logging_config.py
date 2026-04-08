"""Centralized logging configuration for library-mcp."""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(
    level: str | None = None,
    stream: object = sys.stderr,
) -> None:
    """Configure logging for the application.

    Uses LOG_LEVEL env var if level is not explicitly provided.
    Defaults to INFO. Always logs to stderr to avoid polluting
    stdio transport when running as an MCP server.
    """
    log_level = (level or os.environ.get("LOG_LEVEL", "info")).upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Clear any existing handlers to avoid duplicate output
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root.setLevel(numeric_level)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers
    for noisy in ("chromadb", "sentence_transformers", "httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(max(numeric_level, logging.WARNING))
