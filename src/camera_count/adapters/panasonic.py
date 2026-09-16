"""Panasonic cameras.

Every method this adapter can use comes from
``registry/camera_database/panasonic.yaml``, where each entry carries a
citation. Adding a count here means adding a cited registry entry, not writing
code.

``vendor_read_opcodes`` is the allow-list for vendor operations. It is empty
until a vendor read operation is documented for a Panasonic body; while it
is empty, no vendor operation can be sent to one.
"""

from __future__ import annotations

from typing import ClassVar

from camera_count.adapters.base import RegistryAdapter


class PanasonicAdapter(RegistryAdapter):
    """Reads the documented counters for Panasonic bodies."""

    manufacturer_key: ClassVar[str] = "Panasonic"
    vendor_read_opcodes: ClassVar[frozenset[int]] = frozenset()
