"""The camera registry: what is known, and where each claim comes from."""

from __future__ import annotations

from camera_count.registry.loader import (
    CameraRegistry,
    database_path,
    load_default_registry,
    load_registry,
    load_schema,
    schema_path,
    validate_document,
)
from camera_count.registry.models import (
    CameraModel,
    ManufacturerEntry,
    RegisteredMethod,
    make_source_id,
    normalize_name,
)

__all__ = [
    "CameraModel",
    "CameraRegistry",
    "ManufacturerEntry",
    "RegisteredMethod",
    "database_path",
    "load_default_registry",
    "load_registry",
    "load_schema",
    "make_source_id",
    "normalize_name",
    "schema_path",
    "validate_document",
]
