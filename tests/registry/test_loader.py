"""Registry loading, schema validation, and the invariants that protect the guard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from camera_count.core.enums import CountType, VerificationStatus
from camera_count.core.errors import RegistryError
from camera_count.core.models import ShutterReading
from camera_count.registry.loader import (
    CameraRegistry,
    database_path,
    load_registry,
    load_schema,
    validate_document,
)
from camera_count.registry.models import normalize_name

CITATION = {
    "kind": "source_ref",
    "reference": "tests/registry/test_loader.py:1",
    "note": "test fixture",
}


def write_registry(directory: Path, name: str, document: dict[str, Any]) -> Path:
    path = directory / f"{name}.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def documented_method(count_type: str = "mechanical") -> dict[str, Any]:
    return {
        "type": "ptp_property",
        "identifier": "0x1234",
        "count_type": count_type,
        "citation": CITATION,
        "verification_status": "documented",
    }


# --- the shipped database ----------------------------------------------------


def test_bundled_registry_loads_and_validates() -> None:
    registry = load_registry()

    assert registry.entries, "the bundled database must contain manufacturer files"
    assert registry.manufacturers()


def test_every_bundled_file_passes_the_schema() -> None:
    for path in sorted(database_path().glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        validate_document(document, origin=path.name)


def test_every_vendor_id_is_cited() -> None:
    registry = load_registry()

    for entry in registry.entries:
        for vendor in entry.usb_vendor_ids:
            assert vendor.citation.reference
            assert 0 <= vendor.id <= 0xFFFF


def test_schema_is_valid_json_schema() -> None:
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(load_schema())


# --- invariants --------------------------------------------------------------


def test_claiming_an_exact_count_without_a_trusted_method_is_refused(tmp_path: Path) -> None:
    write_registry(
        tmp_path,
        "maker",
        {
            "manufacturer": "Maker",
            "models": [
                {
                    "model": "Body One",
                    "exact_count_available": True,
                    "methods": [{**documented_method(), "verification_status": "unverified"}],
                }
            ],
        },
    )

    with pytest.raises(RegistryError, match="no method is documented"):
        load_registry(tmp_path)


def test_hiding_a_trusted_method_behind_a_false_flag_is_refused(tmp_path: Path) -> None:
    write_registry(
        tmp_path,
        "maker",
        {
            "manufacturer": "Maker",
            "models": [
                {
                    "model": "Body One",
                    "exact_count_available": False,
                    "methods": [documented_method()],
                }
            ],
        },
    )

    with pytest.raises(RegistryError, match="flag must follow the evidence"):
        load_registry(tmp_path)


def test_method_without_a_citation_fails_schema_validation(tmp_path: Path) -> None:
    method = documented_method()
    del method["citation"]
    write_registry(
        tmp_path,
        "maker",
        {
            "manufacturer": "Maker",
            "models": [{"model": "Body One", "exact_count_available": True, "methods": [method]}],
        },
    )

    with pytest.raises(RegistryError, match="schema validation failed"):
        load_registry(tmp_path)


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    write_registry(
        tmp_path,
        "maker",
        {
            "manufacturer": "Maker",
            "models": [
                {
                    "model": "Body One",
                    "exact_count_available": False,
                    "estimated_count": 40000,
                }
            ],
        },
    )

    with pytest.raises(RegistryError, match="schema validation failed"):
        load_registry(tmp_path)


def test_duplicate_models_are_rejected(tmp_path: Path) -> None:
    write_registry(
        tmp_path,
        "maker",
        {
            "manufacturer": "Maker",
            "models": [
                {"model": "Body One", "exact_count_available": False},
                {"model": "body one", "exact_count_available": False},
            ],
        },
    )

    with pytest.raises(RegistryError, match="duplicate model"):
        load_registry(tmp_path)


def test_empty_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="no registry files"):
        load_registry(tmp_path)


def test_oversized_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "huge.yaml"
    path.write_text("notes: " + ("x" * 1_100_000), encoding="utf-8")

    with pytest.raises(RegistryError, match="too large"):
        load_registry(tmp_path)


# --- lookup ------------------------------------------------------------------


@pytest.fixture
def small_registry(tmp_path: Path) -> CameraRegistry:
    write_registry(
        tmp_path,
        "maker",
        {
            "manufacturer": "Maker",
            "manufacturer_aliases": ["MAKER CORPORATION"],
            "usb_vendor_ids": [{"id": 0x1234, "citation": CITATION}],
            "models": [
                {
                    "model": "MAKER BODY_1",
                    "aliases": ["Maker Body One"],
                    "usb_pid": 0x5678,
                    "exact_count_available": True,
                    "methods": [documented_method(), documented_method("electronic")],
                },
                {"model": "Body Two", "exact_count_available": False},
            ],
        },
    )
    return load_registry(tmp_path)


def test_model_lookup_matches_aliases_and_spacing(small_registry: CameraRegistry) -> None:
    assert small_registry.find_model("MAKER CORPORATION", "MAKER BODY 1") is not None
    assert small_registry.find_model("Maker", "Maker Body One") is not None
    assert small_registry.find_model("Maker", "maker  body_1") is not None


def test_model_lookup_does_not_guess(small_registry: CameraRegistry) -> None:
    assert small_registry.find_model("Maker", "BODY_3") is None
    assert small_registry.find_model("Maker", "") is None
    assert small_registry.find_model("Other", "MAKER BODY_1") is None


def test_usb_lookup_uses_vendor_and_product(small_registry: CameraRegistry) -> None:
    assert small_registry.find_by_usb_ids(0x1234, 0x5678)
    assert not small_registry.find_by_usb_ids(0x1234, 0x0001)
    assert small_registry.manufacturer_for_vendor_id(0x1234) == "Maker"


def test_source_ids_are_unique_and_resolvable(small_registry: CameraRegistry) -> None:
    records = list(small_registry.records.values())

    assert len(records) == 2
    assert {record.count_type for record in records} == {
        CountType.MECHANICAL,
        CountType.ELECTRONIC,
    }
    for record in records:
        assert small_registry.resolve(record.source_id) is record


def test_registry_resolver_satisfies_the_reading_guard(
    small_registry: CameraRegistry,
) -> None:
    from camera_count.core.sources import set_source_resolver

    source_id = next(iter(small_registry.records))
    previous = set_source_resolver(small_registry)
    try:
        reading = ShutterReading.from_source(value=42, source_id=source_id)
        assert reading.value == 42
        assert reading.source.verification_status is VerificationStatus.DOCUMENTED
    finally:
        set_source_resolver(previous)


def test_normalize_name_is_conservative() -> None:
    assert normalize_name("NIKON  Z 6_2") == "nikon z 6 2"
    assert normalize_name("  Canon EOS-R6 ") == "canon eos r6"
    assert normalize_name("") == ""
