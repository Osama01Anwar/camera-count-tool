"""One-off: record the research outcome for manufacturers with no method yet.

Kept in the repository so the next person can see that "no entry" is a
researched conclusion rather than an oversight.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DATABASE: Final = REPO_ROOT / "src" / "camera_count" / "registry" / "camera_database"

NO_TAG_NOTE: Final = (
    "ExifTool 13.59 defines no shutter- or actuation-count tag for this "
    "manufacturer. Searched on 2026-09-16 with scripts/research_exiftool_tags.py "
    "over lib/Image/ExifTool/. No exact count can be read from an image file "
    "until a source documents one."
)

NOTES: Final[dict[str, str]] = {
    "sony.yaml": (
        "ExifTool defines several Sony ShutterCount tags, but they are "
        "model-conditional and the source marks some of them as valid only for "
        "certain models - see exiftool/lib/Image/ExifTool/Sony.pm:3339, :3483, "
        ":3490 and the Tag9050a/b/c tables from :7644. Registering them needs "
        "per-model work, so Sony bodies currently report the count as "
        "unavailable rather than risk reporting the wrong number."
    ),
    "fujifilm.yaml": NO_TAG_NOTE
    + " Note that some Fujifilm bodies expose a count of saved images, which is "
    "not an actuation count and must not be registered as one.",
    "olympus_om.yaml": NO_TAG_NOTE,
    "panasonic.yaml": NO_TAG_NOTE,
    "leica.yaml": NO_TAG_NOTE,
    "sigma.yaml": NO_TAG_NOTE,
    "hasselblad.yaml": NO_TAG_NOTE,
    "phase_one.yaml": NO_TAG_NOTE,
}


def wrap(text: str, width: int = 76) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = "  "
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current.rstrip())
            current = "  "
        current += word + " "
    if current.strip():
        lines.append(current.rstrip())
    return lines


def main() -> int:
    changed = 0
    for filename, note in NOTES.items():
        path = DATABASE / filename
        if not path.is_file():
            print(f"skipped (missing): {filename}")
            continue
        text = path.read_text(encoding="utf-8")
        if "\nnotes:" in text:
            print(f"skipped (already has notes): {filename}")
            continue
        block = "notes: >-\n" + "\n".join(wrap(note)) + "\n"
        text = text.replace("models: []", block + "models: []")
        path.write_text(text, encoding="utf-8")
        changed += 1
        print(f"annotated: {filename}")
    print(f"{changed} file(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
