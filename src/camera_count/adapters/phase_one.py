"""Phase One cameras.

Every method this adapter can use comes from
``registry/camera_database/phase_one.yaml``, where each entry carries a
citation. Adding a count here means adding a cited registry entry, not writing
code.

``vendor_read_opcodes`` is the allow-list for vendor operations. It is empty
until a vendor read operation is documented for a Phase One body; while it
is empty, no vendor operation can be sent to one.
"""

from __future__ import annotations

from typing import ClassVar

from camera_count.adapters.base import RegistryAdapter


class PhaseOneAdapter(RegistryAdapter):
    """Reads the documented counters for Phase One bodies."""

    manufacturer_key: ClassVar[str] = "Phase One"
    vendor_read_opcodes: ClassVar[frozenset[int]] = frozenset()
