"""The fallback adapter: identity only, never a count.

When a camera's manufacturer has no registry file, this adapter still lets the
program say what is connected - make, model, serial, firmware, as the device
reports them. It cannot produce a count, and it does not try. There is no
"generic shutter count property" to fall back on, and inventing one is the
exact failure this program exists to avoid.
"""

from __future__ import annotations

from typing import ClassVar

from camera_count.adapters.base import RegistryAdapter
from camera_count.core.messages import (
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    REASON_NO_REGISTRY_ENTRY,
)
from camera_count.core.models import CameraIdentity, CountResult, Unavailable
from camera_count.link import CameraLink
from camera_count.registry.models import CameraModel, ManufacturerEntry


class GenericPtpAdapter(RegistryAdapter):
    """Identifies any camera; counts for none."""

    manufacturer_key: ClassVar[str] = ""
    vendor_read_opcodes: ClassVar[frozenset[int]] = frozenset()

    @property
    def name(self) -> str:
        return "generic_ptp"

    def matches(self, entry: ManufacturerEntry | None) -> bool:  # noqa: ARG002
        """The fallback never claims an entry; the dispatcher chooses it last."""
        return False

    def read_counts(
        self,
        link: CameraLink,  # noqa: ARG002 - interface parameter, deliberately unused
        model: CameraModel | None,  # noqa: ARG002
        identity: CameraIdentity,  # noqa: ARG002
    ) -> tuple[CountResult, ...]:
        return (
            Unavailable(
                message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                reason=REASON_NO_REGISTRY_ENTRY,
            ),
        )
