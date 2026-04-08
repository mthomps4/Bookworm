"""Configuration loading from config.yaml with environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import AppConfig, ChunkingConfig, EmbeddingsConfig, EmbeddingProvider, LibraryConfig, SearchConfig

# Load .env if present
load_dotenv()

_DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from YAML file, then apply environment variable overrides."""
    path = config_path or _DEFAULT_CONFIG_PATH

    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    config = AppConfig.model_validate(raw)
    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: AppConfig) -> None:
    """Override config values with environment variables where set."""
    if v := os.environ.get("BOOKS_PATH"):
        config.library.books_dir = Path(v)
    if v := os.environ.get("CHROMA_PATH"):
        config.library.db_path = Path(v)
    if v := os.environ.get("MANIFEST_PATH"):
        config.library.manifest_path = Path(v)

    if v := os.environ.get("CHUNK_TARGET_TOKENS"):
        config.chunking.target_tokens = int(v)
    if v := os.environ.get("CHUNK_OVERLAP_TOKENS"):
        config.chunking.overlap_tokens = int(v)

    if v := os.environ.get("EMBEDDING_PROVIDER"):
        config.embeddings.provider = EmbeddingProvider(v)
    if v := os.environ.get("EMBEDDING_MODEL"):
        config.embeddings.model = v

    if v := os.environ.get("ALLOWED_FORMATS"):
        config.library.allowed_formats = [f.strip() for f in v.split(",")]

    if v := os.environ.get("SEARCH_DEFAULT_TOP_K"):
        config.search.default_top_k = int(v)
