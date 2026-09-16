"""Collect shutter-count evidence from the ExifTool tag tables.

This is a research aid, not a code generator. It reads the ExifTool Perl
distribution vendored under ``packaging/vendor/exiftool-*`` and reports every
tag whose name looks like an actuation counter, together with the table it
belongs to, its tag id, the exact line number, and any Notes or model
Conditions around it.

A human then decides what earns a registry entry. Nothing here writes to the
registry: "ExifTool has a tag called ShutterCount" is evidence, not a licence to
report a number for every camera on earth.

Run:  python scripts/research_exiftool_tags.py --make Nikon
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
VENDOR: Final = REPO_ROOT / "packaging" / "vendor"

#: Tag names worth looking at. Deliberately broad: the point is to see what
#: exists, including the near misses that must NOT become shutter counts.
INTERESTING: Final = re.compile(
    r"^(ShutterCount\d*|ShutterCounter|MechanicalShutterCount|ShutterReleaseCount\w*|"
    r"TotalShutterReleases|ActuationCount\w*|ImageCount\d*|ImageNumber|FileIndex|"
    r"FileNumber|ExposureCount|ReleaseCount\w*)$"
)

TABLE_RE: Final = re.compile(r"^%Image::ExifTool::(\w+)::(\w+)\s*=\s*\(")
TAG_ID_RE: Final = re.compile(r"^\s{4}(0x[0-9a-fA-F]+|\d+)\s*=>")
NAME_RE: Final = re.compile(r"Name\s*=>\s*'([^']+)'")
NOTES_RE: Final = re.compile(r"Notes\s*=>\s*(?:q\{|')(.*)")
CONDITION_RE: Final = re.compile(r"Condition\s*=>\s*'([^']*)'")
FORMAT_RE: Final = re.compile(r"Format\s*=>\s*'([^']+)'")
WRITABLE_RE: Final = re.compile(r"Writable\s*=>\s*'([^']+)'")


@dataclass(frozen=True)
class Finding:
    """One candidate tag, with everything needed to judge and cite it."""

    make: str
    module: str
    table: str
    tag_id: str
    tag_name: str
    line: int
    citation: str
    data_format: str | None
    condition: str | None
    notes: str
    group1_hint: str

    @property
    def is_counter_name(self) -> bool:
        return self.tag_name.lower().startswith(("shuttercount", "mechanicalshutter"))


def _group1_hint(module: str, table: str) -> str:
    """The family-1 group ExifTool reports for a MakerNotes tag.

    For manufacturer MakerNotes this is the manufacturer module name, which is
    what a registry identifier must use: ``Nikon:ShutterCount``.
    """
    if table.startswith(("Main", "CameraInfo", "ShotInfo", "Tag9", "CameraSettings")):
        return module
    return module


def scan_module(path: Path) -> list[Finding]:
    module = path.stem
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    findings: list[Finding] = []
    table = "(file scope)"
    tag_id = "?"

    for index, line in enumerate(lines, start=1):
        table_match = TABLE_RE.match(line)
        if table_match:
            table = table_match.group(2)
            continue

        id_match = TAG_ID_RE.match(line)
        if id_match:
            tag_id = id_match.group(1)

        name_match = NAME_RE.search(line)
        if not name_match:
            continue
        name = name_match.group(1)
        if not INTERESTING.match(name):
            continue

        window = "\n".join(lines[max(0, index - 12) : min(len(lines), index + 12)])
        notes = " ".join(
            NOTES_RE.search(fragment).group(1).strip()  # type: ignore[union-attr]
            for fragment in window.splitlines()
            if NOTES_RE.search(fragment)
        )
        condition = None
        for fragment in window.splitlines():
            found = CONDITION_RE.search(fragment)
            if found and ("Model" in found.group(1) or "Make" in found.group(1)):
                condition = found.group(1)
                break

        data_format = None
        for fragment in lines[index - 1 : min(len(lines), index + 6)]:
            found_format = FORMAT_RE.search(fragment) or WRITABLE_RE.search(fragment)
            if found_format:
                data_format = found_format.group(1)
                break

        findings.append(
            Finding(
                make=module,
                module=f"lib/Image/ExifTool/{path.name}",
                table=table,
                tag_id=tag_id,
                tag_name=name,
                line=index,
                citation=f"exiftool/lib/Image/ExifTool/{path.name}:{index}",
                data_format=data_format,
                condition=condition,
                notes=notes.strip(),
                group1_hint=_group1_hint(module, table),
            )
        )
    return findings


def find_vendor_lib() -> Path:
    candidates = sorted(VENDOR.glob("exiftool-*/lib/Image/ExifTool"))
    if not candidates:
        raise SystemExit(
            "no vendored ExifTool source found. Run:\n"
            "  python scripts/fetch_exiftool.py --mode source"
        )
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make", action="append", help="Limit to these modules.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--counters-only",
        action="store_true",
        help="Only tags whose name is a shutter-count name.",
    )
    args = parser.parse_args()

    library = find_vendor_lib()
    modules = sorted(library.glob("*.pm"))
    if args.make:
        wanted = {name.casefold() for name in args.make}
        modules = [path for path in modules if path.stem.casefold() in wanted]

    findings: list[Finding] = []
    for path in modules:
        findings.extend(scan_module(path))
    if args.counters_only:
        findings = [item for item in findings if item.is_counter_name]

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
        return 0

    by_make: dict[str, list[Finding]] = {}
    for item in findings:
        by_make.setdefault(item.make, []).append(item)

    for make, items in sorted(by_make.items()):
        print(f"\n### {make}  ({len(items)} candidates)")
        for item in items:
            print(f"  {item.tag_name:<24} {item.tag_id:<10} table={item.table}")
            print(f"      cite  : {item.citation}")
            if item.data_format:
                print(f"      format: {item.data_format}")
            if item.condition:
                print(f"      model : {item.condition}")
            if item.notes:
                print(f"      notes : {item.notes[:200]}")
    print(f"\n{len(findings)} candidates across {len(by_make)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
