"""Adapters read what the registry documents, and nothing else."""

from __future__ import annotations

import pytest

from camera_count.adapters import ADAPTERS, GENERIC_ADAPTER, select_adapter
from camera_count.adapters.base import RegistryAdapter
from camera_count.core.enums import (
    CitationKind,
    CountType,
    MethodType,
    ValueSource,
    VerificationStatus,
)
from camera_count.core.messages import (
    CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT,
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
)
from camera_count.core.models import CameraIdentity, ShutterReading, Unavailable
from camera_count.core.sources import Citation, set_source_resolver
from camera_count.diagnostics.log import TransactionLog
from camera_count.ptp.constants import ResponseCode
from camera_count.ptp.transport import TransactionResult
from camera_count.registry import load_registry
from camera_count.registry.models import (
    CameraModel,
    ManufacturerEntry,
    RegisteredMethod,
    ValueSpec,
)

CITATION = Citation(kind=CitationKind.SOURCE_REF, reference="tests/adapters:1", note="test")


class FakeLink:
    """A camera link that answers from a script. Never touches hardware."""

    def __init__(
        self,
        *,
        properties: dict[int, int] | None = None,
        operations: dict[int, TransactionResult] | None = None,
        identity: CameraIdentity | None = None,
    ) -> None:
        self._properties = properties or {}
        self._operations = operations or {}
        self._identity = identity or CameraIdentity(manufacturer="Maker", model="Body One")
        self._log = TransactionLog(transport="fake")
        self.permitted: frozenset[int] = frozenset()

    @property
    def name(self) -> str:
        return "fake"

    @property
    def log(self) -> TransactionLog:
        return self._log

    @property
    def allowed_opcodes(self) -> frozenset[int]:
        return self.permitted

    def permit_operations(self, opcodes: frozenset[int]) -> None:
        self.permitted = self.permitted | opcodes

    def identity(self) -> CameraIdentity:
        return self._identity

    def read_device_property(self, code: int) -> tuple[int, str] | None:
        if code not in self._properties:
            return None
        record = self._log.record(operation=f"property 0x{code:04X}", opcode=code)
        return self._properties[code], record.reference

    def execute_read_operation(
        self, code: int, parameters: tuple[int, ...] = (), *, expect_data: bool = False
    ) -> TransactionResult:
        record = self._log.record(operation=f"operation 0x{code:04X}", opcode=code)
        assert record.reference
        return self._operations.get(
            code, TransactionResult(response_code=ResponseCode.OPERATION_NOT_SUPPORTED.value)
        )


def method(
    *,
    source_id: str = "maker/body-one#0",
    method_type: MethodType = MethodType.PTP_PROPERTY,
    identifier: str = "0xD1A3",
    count_type: CountType = CountType.MECHANICAL,
    status: VerificationStatus = VerificationStatus.DOCUMENTED,
    firmware_range: str | None = None,
    value_spec: ValueSpec | None = None,
) -> RegisteredMethod:
    return RegisteredMethod(
        source_id=source_id,
        method_type=method_type,
        identifier=identifier,
        count_type=count_type,
        verification_status=status,
        citation=CITATION,
        firmware_range=firmware_range,
        value_spec=value_spec,
    )


def model_with(*methods: RegisteredMethod) -> CameraModel:
    return CameraModel(
        manufacturer="Maker",
        model="Body One",
        exact_count_available=bool(methods),
        methods=methods,
    )


@pytest.fixture
def resolver_for_model():
    def install(model: CameraModel) -> None:
        records = {record.source_id: record for record in model.source_records()}
        set_source_resolver(type("R", (), {"resolve": lambda self, i: records.get(i)})())

    previous = set_source_resolver(None)
    yield install
    set_source_resolver(previous)


IDENTITY = CameraIdentity(manufacturer="Maker", model="Body One", firmware="1.40")


# --- the happy path ----------------------------------------------------------


def test_documented_property_produces_a_cited_reading(resolver_for_model) -> None:
    model = model_with(method())
    resolver_for_model(model)
    link = FakeLink(properties={0xD1A3: 48_120})

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert len(results) == 1
    reading = results[0]
    assert isinstance(reading, ShutterReading)
    assert reading.value == 48_120
    assert reading.count_type is CountType.MECHANICAL
    assert reading.source.citation.reference
    assert link.log.find(reading.transaction_ref or "") is not None


def test_each_counter_type_gets_its_own_reading(resolver_for_model) -> None:
    model = model_with(
        method(source_id="maker/body-one#0", identifier="0xD1A3"),
        method(
            source_id="maker/body-one#1",
            identifier="0xD1A4",
            count_type=CountType.ELECTRONIC,
        ),
    )
    resolver_for_model(model)
    link = FakeLink(properties={0xD1A3: 100, 0xD1A4: 250})

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    values = {r.count_type: r.value for r in results if isinstance(r, ShutterReading)}
    assert values == {CountType.MECHANICAL: 100, CountType.ELECTRONIC: 250}


def test_operation_method_reads_the_documented_response_parameter(resolver_for_model) -> None:
    model = model_with(
        method(
            method_type=MethodType.PTP_OPERATION,
            identifier="0x9999",
            value_spec=ValueSpec(source=ValueSource.RESPONSE_PARAMETER, index=1),
        )
    )
    resolver_for_model(model)
    link = FakeLink(
        operations={
            0x9999: TransactionResult(
                response_code=ResponseCode.OK.value, response_parameters=(7, 31_415)
            )
        }
    )

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], ShutterReading)
    assert results[0].value == 31_415


def test_operation_method_reads_the_documented_data_offset(resolver_for_model) -> None:
    model = model_with(
        method(
            method_type=MethodType.PTP_OPERATION,
            identifier="0x9999",
            value_spec=ValueSpec(source=ValueSource.DATA_UINT32, offset=4),
        )
    )
    resolver_for_model(model)
    payload = b"\x00\x00\x00\x00" + (12_345).to_bytes(4, "little")
    link = FakeLink(
        operations={0x9999: TransactionResult(response_code=ResponseCode.OK.value, data=payload)}
    )

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], ShutterReading)
    assert results[0].value == 12_345


# --- refusing to guess -------------------------------------------------------


def test_unknown_model_yields_unavailable_not_a_fallback_read() -> None:
    link = FakeLink(properties={0xD1A3: 48_120})

    results = RegistryAdapter().read_counts(link, None, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert results[0].message == EXACT_SHUTTER_COUNT_NOT_AVAILABLE


def test_model_without_a_trusted_method_is_never_probed() -> None:
    model = model_with()
    link = FakeLink(properties={0xD1A3: 48_120})

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert link.log.records == ()


def test_unverified_method_is_not_used(resolver_for_model) -> None:
    model = CameraModel(
        manufacturer="Maker",
        model="Body One",
        exact_count_available=False,
        methods=(method(status=VerificationStatus.UNVERIFIED),),
    )
    link = FakeLink(properties={0xD1A3: 48_120})

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert link.log.records == ()


def test_firmware_outside_the_documented_range_is_refused(resolver_for_model) -> None:
    model = model_with(method(firmware_range=">=2.00"))
    resolver_for_model(model)
    link = FakeLink(properties={0xD1A3: 48_120})

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert "firmware" in results[0].reason
    assert link.log.records == ()


def test_camera_that_does_not_expose_the_property_says_so(resolver_for_model) -> None:
    model = model_with(method())
    resolver_for_model(model)
    link = FakeLink(properties={})

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert results[0].message == CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT


def test_makernote_only_model_points_at_image_mode(resolver_for_model) -> None:
    model = model_with(
        method(method_type=MethodType.MAKERNOTE_FIELD, identifier="Nikon:ShutterCount")
    )
    resolver_for_model(model)
    link = FakeLink()

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert "camera-count exif" in results[0].reason


def test_service_interface_method_is_reported_not_attempted(resolver_for_model) -> None:
    model = model_with(method(method_type=MethodType.SERVICE_INTERFACE, identifier="0x1"))
    resolver_for_model(model)
    link = FakeLink()

    results = RegistryAdapter().read_counts(link, model, IDENTITY)

    assert isinstance(results[0], Unavailable)
    assert "service interface" in results[0].reason
    assert link.log.records == ()


# --- the fallback ------------------------------------------------------------


def test_generic_adapter_never_produces_a_count() -> None:
    link = FakeLink(properties={0xD1A3: 48_120})
    model = model_with(method())

    results = GENERIC_ADAPTER.read_counts(link, model, IDENTITY)

    assert all(isinstance(result, Unavailable) for result in results)
    assert link.log.records == ()


def test_dispatcher_falls_back_when_no_entry_matches() -> None:
    assert select_adapter(None) is GENERIC_ADAPTER


def test_dispatcher_picks_the_adapter_for_the_entry() -> None:
    entry = ManufacturerEntry(manufacturer="Nikon")

    adapter = select_adapter(entry)

    assert adapter.manufacturer_key == "Nikon"


def test_every_registry_manufacturer_has_an_adapter() -> None:
    registry = load_registry()
    adapter_keys = {adapter.manufacturer_key for adapter in ADAPTERS}

    missing = [
        entry.manufacturer for entry in registry.entries if entry.manufacturer not in adapter_keys
    ]

    assert not missing, f"registry manufacturers without an adapter: {missing}"


def test_no_adapter_permits_a_vendor_operation_without_a_cited_method() -> None:
    """Allow-lists start empty. A non-empty one must be justified in review."""
    for adapter in (*ADAPTERS, GENERIC_ADAPTER):
        assert adapter.allowed_opcodes == frozenset(), (
            f"{adapter.name} permits vendor operations; every code needs a citation "
            "in the registry and a note in docs/protocols.md"
        )
