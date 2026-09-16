"""Per-manufacturer adapters and the dispatcher that picks one."""

from __future__ import annotations

from camera_count.adapters.base import RegistryAdapter
from camera_count.adapters.canon import CanonAdapter
from camera_count.adapters.fujifilm import FujifilmAdapter
from camera_count.adapters.generic_ptp import GenericPtpAdapter
from camera_count.adapters.hasselblad import HasselbladAdapter
from camera_count.adapters.leica import LeicaAdapter
from camera_count.adapters.nikon import NikonAdapter
from camera_count.adapters.olympus_om import OlympusOmAdapter
from camera_count.adapters.panasonic import PanasonicAdapter
from camera_count.adapters.pentax_ricoh import PentaxRicohAdapter
from camera_count.adapters.phase_one import PhaseOneAdapter
from camera_count.adapters.sigma import SigmaAdapter
from camera_count.adapters.sony import SonyAdapter
from camera_count.registry.models import ManufacturerEntry

#: Every manufacturer adapter. The fallback is deliberately not in this list.
ADAPTERS: tuple[RegistryAdapter, ...] = (
    CanonAdapter(),
    NikonAdapter(),
    SonyAdapter(),
    FujifilmAdapter(),
    PanasonicAdapter(),
    OlympusOmAdapter(),
    PentaxRicohAdapter(),
    LeicaAdapter(),
    SigmaAdapter(),
    HasselbladAdapter(),
    PhaseOneAdapter(),
)

GENERIC_ADAPTER: RegistryAdapter = GenericPtpAdapter()


def select_adapter(entry: ManufacturerEntry | None) -> RegistryAdapter:
    """Pick the adapter for a registry entry, or the identity-only fallback."""
    for adapter in ADAPTERS:
        if adapter.matches(entry):
            return adapter
    return GENERIC_ADAPTER


__all__ = [
    "ADAPTERS",
    "GENERIC_ADAPTER",
    "CanonAdapter",
    "FujifilmAdapter",
    "GenericPtpAdapter",
    "HasselbladAdapter",
    "LeicaAdapter",
    "NikonAdapter",
    "OlympusOmAdapter",
    "PanasonicAdapter",
    "PentaxRicohAdapter",
    "PhaseOneAdapter",
    "RegistryAdapter",
    "SigmaAdapter",
    "SonyAdapter",
    "select_adapter",
]
