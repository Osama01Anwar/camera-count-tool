"""The build fails if shipped code learns to hedge.

Estimation vocabulary has no place in src/. The single permitted occurrence is
the mandated disclaimer literal in core/messages.py, which is checked here by
exact position so it cannot be smuggled in anywhere else.
"""

from __future__ import annotations

import pytest

from camera_count.core.messages import UNAVAILABLE_DISCLAIMER
from tests.conftest import SRC_ROOT, iter_source_files

FORBIDDEN_TERMS = ("estimat", "approx", "probab", "confidence", "likely")

#: (relative path, exact literal that may contain a forbidden term)
ALLOWED_LITERALS: dict[str, tuple[str, ...]] = {
    "core/messages.py": (UNAVAILABLE_DISCLAIMER,),
}


def _strip_allowed(relative: str, text: str) -> str:
    for literal in ALLOWED_LITERALS.get(relative, ()):
        text = text.replace(literal, "<allowlisted literal>")
    return text


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_shipped_code_contains_no_estimation_vocabulary(term: str) -> None:
    offenders: list[str] = []
    for path in iter_source_files((".py", ".yaml", ".yml", ".json", ".ui", ".qss")):
        relative = path.relative_to(SRC_ROOT).as_posix()
        text = _strip_allowed(relative, path.read_text(encoding="utf-8"))
        for number, line in enumerate(text.splitlines(), start=1):
            if term in line.lower():
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert not offenders, f"forbidden term {term!r} found in shipped code:\n" + "\n".join(offenders)


def test_disclaimer_literal_lives_in_exactly_one_module() -> None:
    holders = [
        path.relative_to(SRC_ROOT).as_posix()
        for path in iter_source_files((".py",))
        if UNAVAILABLE_DISCLAIMER in path.read_text(encoding="utf-8")
    ]
    assert holders == ["core/messages.py"], (
        "the disclaimer literal must be defined once in core/messages.py and "
        f"imported everywhere else; found it in {holders}"
    )
