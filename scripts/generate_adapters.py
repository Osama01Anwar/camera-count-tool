"""Generate the per-manufacturer adapter modules.

Each adapter is deliberately thin: the mechanism lives in
``camera_count.adapters.base`` and the knowledge lives in the camera registry,
where every claim carries a citation. A module here declares which registry
manufacturer it serves and which vendor read operations it is allowed to send.

Run this only when adding a manufacturer. Editing a generated file by hand is
fine - this script will not overwrite one that already exists.
"""

from __future__ import annotations

from pathlib import Path

ADAPTERS: list[tuple[str, str, str, str]] = [
    # module, class prefix, registry manufacturer, registry file
    ("canon", "Canon", "Canon", "canon.yaml"),
    ("nikon", "Nikon", "Nikon", "nikon.yaml"),
    ("sony", "Sony", "Sony", "sony.yaml"),
    ("fujifilm", "Fujifilm", "Fujifilm", "fujifilm.yaml"),
    ("panasonic", "Panasonic", "Panasonic", "panasonic.yaml"),
    ("olympus_om", "OlympusOm", "Olympus / OM System", "olympus_om.yaml"),
    ("pentax_ricoh", "PentaxRicoh", "Pentax / Ricoh", "pentax_ricoh.yaml"),
    ("leica", "Leica", "Leica", "leica.yaml"),
    ("sigma", "Sigma", "Sigma", "sigma.yaml"),
    ("hasselblad", "Hasselblad", "Hasselblad", "hasselblad.yaml"),
    ("phase_one", "PhaseOne", "Phase One", "phase_one.yaml"),
]

TEMPLATE = '''"""{manufacturer} cameras.

Every method this adapter can use comes from
``registry/camera_database/{registry_file}``, where each entry carries a
citation. Adding a count here means adding a cited registry entry, not writing
code.

``vendor_read_opcodes`` is the allow-list for vendor operations. It is empty
until a vendor read operation is documented for a {manufacturer} body; while it
is empty, no vendor operation can be sent to one.
"""

from __future__ import annotations

from typing import ClassVar

from camera_count.adapters.base import RegistryAdapter


class {class_prefix}Adapter(RegistryAdapter):
    """Reads the documented counters for {manufacturer} bodies."""

    manufacturer_key: ClassVar[str] = "{manufacturer}"
    vendor_read_opcodes: ClassVar[frozenset[int]] = frozenset()
'''


def main() -> int:
    package = Path(__file__).resolve().parents[1] / "src" / "camera_count" / "adapters"
    package.mkdir(parents=True, exist_ok=True)
    written = 0
    for module, class_prefix, manufacturer, registry_file in ADAPTERS:
        path = package / f"{module}.py"
        if path.exists():
            continue
        path.write_text(
            TEMPLATE.format(
                manufacturer=manufacturer,
                class_prefix=class_prefix,
                registry_file=registry_file,
            ),
            encoding="utf-8",
        )
        written += 1
    print(f"wrote {written} adapter module(s) into {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
