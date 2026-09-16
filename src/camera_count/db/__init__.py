"""The local SQLite results database."""

from __future__ import annotations

from camera_count.db.repository import (
    APP_NAME,
    DATABASE_FILENAME,
    SCHEMA_VERSION,
    Database,
    StoredInspection,
    default_database_path,
)

__all__ = [
    "APP_NAME",
    "DATABASE_FILENAME",
    "SCHEMA_VERSION",
    "Database",
    "StoredInspection",
    "default_database_path",
]
