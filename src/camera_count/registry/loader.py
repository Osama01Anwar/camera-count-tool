"""Load, validate and query the camera registry.

The registry is the project's evidence base. Loading it is strict on purpose: a
file that fails the schema, a model claiming an exact count without a trusted
method, or two entries fighting over one source id all raise
:class:`RegistryError` rather than degrading quietly.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Final

import yaml

from camera_count.core.enums import (
    CitationKind,
    CountType,
    MethodType,
    Protocol,
    ValueSource,
    VerificationStatus,
)
from camera_count.core.errors import RegistryError
from camera_count.core.sources import Citation, SourceRecord, set_source_resolver
from camera_count.registry.models import (
    CameraModel,
    ManufacturerEntry,
    RegisteredMethod,
    ValueSpec,
    VendorId,
    make_source_id,
)

#: Registry files are ours, but they are still parsed under a bound.
MAX_REGISTRY_FILE_BYTES: Final = 1_048_576

_SCHEMA_FILENAME: Final = "camera_model.schema.json"
_DATABASE_DIRNAME: Final = "camera_database"


def schema_path() -> Path:
    return Path(str(resources.files("camera_count.registry") / _SCHEMA_FILENAME))


def database_path() -> Path:
    return Path(str(resources.files("camera_count.registry") / _DATABASE_DIRNAME))


def load_schema() -> dict[str, Any]:
    path = schema_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot read the registry schema at {path}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class CameraRegistry:
    """Everything the program knows about cameras, indexed for lookup."""

    entries: tuple[ManufacturerEntry, ...] = ()
    records: dict[str, SourceRecord] = field(default_factory=dict)

    # -- resolver protocol ---------------------------------------------------

    def resolve(self, source_id: str) -> SourceRecord | None:
        return self.records.get(source_id)

    # -- queries -------------------------------------------------------------

    def iter_models(self) -> Iterator[tuple[ManufacturerEntry, CameraModel]]:
        for entry in self.entries:
            for model in entry.models:
                yield entry, model

    def manufacturers(self) -> tuple[str, ...]:
        return tuple(entry.manufacturer for entry in self.entries)

    def find_entry(self, reported_manufacturer: str) -> ManufacturerEntry | None:
        for entry in self.entries:
            if entry.matches_manufacturer(reported_manufacturer):
                return entry
        return None

    def find_model(
        self, reported_manufacturer: str | None, reported_model: str | None
    ) -> CameraModel | None:
        """Find a model by reported names. Returns None rather than guessing.

        An exact model entry always wins. A manufacturer-wide entry is used
        only when no exact entry matches, and only when the manufacturer itself
        is known - it is never applied across makes.
        """
        if not reported_model:
            return None
        candidates: Sequence[ManufacturerEntry]
        if reported_manufacturer:
            entry = self.find_entry(reported_manufacturer)
            candidates = (entry,) if entry is not None else ()
        else:
            candidates = self.entries

        for candidate in candidates:
            for model in candidate.models:
                if model.matches_name(reported_model):
                    return model

        if reported_manufacturer:
            for candidate in candidates:
                for model in candidate.models:
                    if model.is_wildcard:
                        return model
        return None

    def find_by_usb_ids(self, vid: int, pid: int) -> tuple[CameraModel, ...]:
        """Models registered with this exact vendor/product pair."""
        return tuple(
            model
            for entry, model in self.iter_models()
            if model.usb_pid == pid
            and (model.usb_vid == vid if model.usb_vid is not None else entry.owns_vendor_id(vid))
        )

    def vendor_ids(self) -> dict[int, str]:
        """Every known vendor id mapped to its manufacturer name."""
        mapping: dict[int, str] = {}
        for entry in self.entries:
            for vendor in entry.usb_vendor_ids:
                mapping[vendor.id] = entry.manufacturer
        return mapping

    def manufacturer_for_vendor_id(self, vid: int) -> str | None:
        return self.vendor_ids().get(vid)

    @property
    def model_count(self) -> int:
        return sum(len(entry.models) for entry in self.entries)

    @property
    def documented_model_count(self) -> int:
        return sum(1 for _, model in self.iter_models() if model.exact_count_available)


# --- parsing -----------------------------------------------------------------


def _parse_citation(raw: dict[str, Any], where: str) -> Citation:
    try:
        return Citation(
            kind=CitationKind(raw["kind"]),
            reference=str(raw["reference"]),
            note=raw.get("note"),
        )
    except (KeyError, ValueError) as exc:
        raise RegistryError(f"{where}: invalid citation: {exc}") from exc


def _parse_method(
    raw: dict[str, Any], *, manufacturer: str, model_name: str, index: int
) -> RegisteredMethod:
    where = f"{manufacturer} {model_name} method[{index}]"
    citation = _parse_citation(raw["citation"], where)
    value_spec: ValueSpec | None = None
    if "value" in raw:
        try:
            value_spec = ValueSpec(
                source=ValueSource(raw["value"]["source"]),
                index=int(raw["value"].get("index", 0)),
                offset=int(raw["value"].get("offset", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryError(f"{where}: invalid value location: {exc}") from exc
    try:
        method = RegisteredMethod(
            source_id=make_source_id(manufacturer, model_name, index),
            method_type=MethodType(raw["type"]),
            identifier=str(raw["identifier"]),
            count_type=CountType(raw["count_type"]),
            verification_status=VerificationStatus(raw["verification_status"]),
            citation=citation,
            firmware_range=raw.get("firmware_range"),
            value_spec=value_spec,
            invalid_values=tuple(int(item) for item in raw.get("invalid_values", [])),
            notes=raw.get("notes"),
        )
    except (KeyError, ValueError) as exc:
        raise RegistryError(f"{where}: {exc}") from exc

    if method.method_type is MethodType.PTP_OPERATION and method.value_spec is None:
        raise RegistryError(
            f"{where}: a ptp_operation method must say where the integer is; "
            "add a 'value' block sourced from the same documentation as the citation"
        )
    return method


def _parse_model(raw: dict[str, Any], *, manufacturer: str) -> CameraModel:
    model_name = str(raw["model"])
    where = f"{manufacturer} {model_name}"
    methods = tuple(
        _parse_method(item, manufacturer=manufacturer, model_name=model_name, index=index)
        for index, item in enumerate(raw.get("methods", []))
    )
    exact_available = bool(raw["exact_count_available"])
    trusted = tuple(method for method in methods if method.is_trusted())
    if exact_available and not trusted:
        raise RegistryError(
            f"{where}: exact_count_available is true but no method is documented "
            "or hardware_verified"
        )
    if trusted and not exact_available:
        raise RegistryError(
            f"{where}: has a trusted method but exact_count_available is false; "
            "the flag must follow the evidence"
        )
    return CameraModel(
        manufacturer=manufacturer,
        model=model_name,
        aliases=tuple(raw.get("aliases", [])),
        usb_vid=raw.get("usb_vid"),
        usb_pid=raw.get("usb_pid"),
        protocol=Protocol(raw.get("protocol", Protocol.PTP_USB.value)),
        exact_count_available=exact_available,
        methods=methods,
        limitations=tuple(raw.get("limitations", [])),
        notes=raw.get("notes"),
    )


def _parse_vendor_ids(raw: dict[str, Any], *, manufacturer: str) -> tuple[VendorId, ...]:
    vendors: list[VendorId] = []
    for index, item in enumerate(raw.get("usb_vendor_ids", [])):
        where = f"{manufacturer} usb_vendor_ids[{index}]"
        try:
            vendors.append(
                VendorId(
                    id=int(item["id"]),
                    citation=_parse_citation(item["citation"], where),
                    note=item.get("note"),
                )
            )
        except (KeyError, ValueError) as exc:
            raise RegistryError(f"{where}: {exc}") from exc
    return tuple(vendors)


def _parse_entry(raw: dict[str, Any], *, origin: Path) -> ManufacturerEntry:
    manufacturer = str(raw["manufacturer"])
    vendor_ids = _parse_vendor_ids(raw, manufacturer=manufacturer)
    models = tuple(_parse_model(item, manufacturer=manufacturer) for item in raw.get("models", []))
    seen: set[str] = set()
    for model in models:
        key = model.model.casefold()
        if key in seen:
            raise RegistryError(f"{origin.name}: duplicate model entry {model.model!r}")
        seen.add(key)
    return ManufacturerEntry(
        manufacturer=manufacturer,
        aliases=tuple(raw.get("manufacturer_aliases", [])),
        usb_vendor_ids=vendor_ids,
        models=models,
        notes=raw.get("notes"),
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size > MAX_REGISTRY_FILE_BYTES:
        raise RegistryError(f"{path.name}: registry file is too large ({size} bytes)")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"{path.name}: cannot parse YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RegistryError(f"{path.name}: expected a mapping at the top level")
    return data


def validate_document(raw: dict[str, Any], *, origin: str) -> None:
    """Validate one parsed registry document against the JSON Schema."""
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(load_schema())
    problems = sorted(validator.iter_errors(raw), key=lambda error: list(error.path))
    if problems:
        detail = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in problems[:5]
        )
        raise RegistryError(f"{origin}: schema validation failed: {detail}")


def load_registry(directory: Path | None = None) -> CameraRegistry:
    """Load every ``*.yaml`` file in ``directory`` (default: the bundled database)."""
    source_dir = directory or database_path()
    if not source_dir.is_dir():
        raise RegistryError(f"camera database directory not found: {source_dir}")

    entries: list[ManufacturerEntry] = []
    records: dict[str, SourceRecord] = {}
    for path in sorted(source_dir.glob("*.yaml")):
        raw = _read_yaml(path)
        validate_document(raw, origin=path.name)
        entry = _parse_entry(raw, origin=path)
        entries.append(entry)
        for model in entry.models:
            for record in model.source_records():
                if record.source_id in records:
                    raise RegistryError(f"{path.name}: duplicate source id {record.source_id!r}")
                records[record.source_id] = record

    if not entries:
        raise RegistryError(f"no registry files found in {source_dir}")

    seen_manufacturers: set[str] = set()
    for entry in entries:
        key = entry.manufacturer.casefold()
        if key in seen_manufacturers:
            raise RegistryError(f"duplicate manufacturer entry: {entry.manufacturer}")
        seen_manufacturers.add(key)

    return CameraRegistry(entries=tuple(entries), records=records)


_cached: CameraRegistry | None = None


def load_default_registry(*, install: bool = True, force: bool = False) -> CameraRegistry:
    """Load the bundled registry once and install it as the source resolver."""
    global _cached  # noqa: PLW0603
    if _cached is None or force:
        _cached = load_registry()
    if install:
        set_source_resolver(_cached)
    return _cached
