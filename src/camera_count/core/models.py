"""Result types.

The one rule this module exists to enforce: a :class:`ShutterReading` can only
come into existence through :meth:`ShutterReading.from_source`, which requires a
source id that resolves to a trusted registry entry. Every other path raises.
There is deliberately no way to attach a number to a counter slot without a
citation behind it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

from camera_count.core.enums import CountType, Protocol
from camera_count.core.errors import (
    ForbiddenConstructionError,
    UnverifiedSourceError,
    ValueOutOfBoundsError,
)
from camera_count.core.messages import (
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    NOT_AVAILABLE,
    REASON_NO_REGISTRY_ENTRY,
    RESULT_MESSAGES,
    unavailable_line,
)
from camera_count.core.sources import SourceRecord, resolve_source

#: Protocol-level upper bound for a 32-bit unsigned counter. This is a bound on
#: what the wire format can carry, not a judgement about plausible wear.
UINT32_MAX: Final = 0xFFFFFFFF

_FACTORY_TOKEN: Final[object] = object()


def validate_count_value(value: object) -> int:
    """Return ``value`` as a validated counter integer, or raise.

    Rejects: non-integers, booleans, negatives, and anything wider than the
    32-bit unsigned range the protocol can carry.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueOutOfBoundsError(f"count must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValueOutOfBoundsError(f"count must not be negative, got {value}")
    if value > UINT32_MAX:
        raise ValueOutOfBoundsError(f"count exceeds the 32-bit protocol bound: {value}")
    return value


@dataclass(frozen=True, slots=True)
class ShutterReading:
    """One exact counter value, inseparable from the source that produced it."""

    value: int
    source: SourceRecord
    transaction_ref: str | None = None
    _token: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _FACTORY_TOKEN:
            raise ForbiddenConstructionError(
                "ShutterReading must be created with ShutterReading.from_source(); "
                "direct construction is not permitted"
            )
        validate_count_value(self.value)

    @classmethod
    def from_source(
        cls,
        *,
        value: int,
        source_id: str,
        transaction_ref: str | None = None,
    ) -> ShutterReading:
        """Create a reading from a validated integer and a trusted source id.

        Raises:
            UnknownSourceError: the id is not in the camera registry.
            UnverifiedSourceError: the entry exists but is not documented or
                hardware-verified.
            ValueOutOfBoundsError: the integer failed validation.
        """
        record = resolve_source(source_id)
        if not record.is_trusted():
            raise UnverifiedSourceError(
                f"source {record.source_id!r} has verification status "
                f"{record.verification_status.value!r}; only documented or "
                "hardware_verified sources may produce a reading"
            )
        return cls(
            value=validate_count_value(value),
            source=record,
            transaction_ref=transaction_ref,
            _token=_FACTORY_TOKEN,
        )

    @property
    def count_type(self) -> CountType:
        """The counter kind, taken from the registry - never chosen by a caller."""
        return self.source.count_type

    @property
    def source_id(self) -> str:
        return self.source.source_id

    def display_value(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Unavailable:
    """A successful result that carries no number.

    ``message`` must be one of the fixed result messages. ``reason`` explains
    which check stopped short. The disclaimer is always appended on display.
    """

    message: str
    reason: str
    count_type: CountType | None = None

    def __post_init__(self) -> None:
        if self.message not in RESULT_MESSAGES:
            raise ValueError(
                f"unavailable message must be one of the fixed result messages, "
                f"got {self.message!r}"
            )
        if not self.reason.strip():
            raise ValueError("unavailable reason must not be empty")

    def display_value(self) -> str:
        return NOT_AVAILABLE

    def display_line(self) -> str:
        return unavailable_line(self.message, self.reason)


type CountResult = ShutterReading | Unavailable


@dataclass(frozen=True, slots=True)
class CounterSlot:
    """One counter kind and whatever we have for it."""

    count_type: CountType
    result: CountResult

    @property
    def has_value(self) -> bool:
        return isinstance(self.result, ShutterReading)


def build_counter_slots(
    results: Iterable[CountResult],
    *,
    absent_reason: str = REASON_NO_REGISTRY_ENTRY,
) -> tuple[CounterSlot, ...]:
    """Place each reading in its own counter slot; fill the rest with NOT AVAILABLE.

    Counters are never merged and never summed. A camera that reports only a
    mechanical count gets exactly one populated slot.
    """
    by_type: dict[CountType, CountResult] = {}
    for result in results:
        key = result.count_type
        if key is None:
            continue
        if isinstance(result, ShutterReading) or key not in by_type:
            by_type[key] = result
    return tuple(
        CounterSlot(
            count_type=count_type,
            result=by_type.get(
                count_type,
                Unavailable(
                    message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                    reason=absent_reason,
                    count_type=count_type,
                ),
            ),
        )
        for count_type in CountType
    )


@dataclass(frozen=True, slots=True)
class CameraIdentity:
    """What the camera said about itself. Unknown fields stay ``None``."""

    manufacturer: str | None = None
    model: str | None = None
    serial: str | None = None
    firmware: str | None = None
    protocol: Protocol = Protocol.UNKNOWN

    @staticmethod
    def _display(value: str | None) -> str:
        return value if value else NOT_AVAILABLE

    def display_manufacturer(self) -> str:
        return self._display(self.manufacturer)

    def display_model(self) -> str:
        return self._display(self.model)

    def display_serial(self) -> str:
        return self._display(self.serial)

    def display_firmware(self) -> str:
        return self._display(self.firmware)

    @property
    def is_identified(self) -> bool:
        return bool(self.manufacturer and self.model)


@dataclass(frozen=True, slots=True)
class NonAuthoritativeCounter:
    """A counter that exists in the data but may never fill a shutter-count slot.

    Image numbers, file indexes and frame counters live here. The value is kept
    so the report can show what was seen, always under the image-counter notice.
    """

    label: str
    value: str
    origin: str

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("non-authoritative counter needs a label")


def first_reading(results: Sequence[CountResult]) -> ShutterReading | None:
    """Return the first actual reading in ``results``, if any."""
    for result in results:
        if isinstance(result, ShutterReading):
            return result
    return None
