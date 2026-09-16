"""Firmware range matching.

A method documented for one firmware range must not be used on a body outside
it. When the range cannot be evaluated - an unparseable spec, or a camera that
did not report its firmware - the answer is "no". Refusing to read is always
safer than reading the wrong address and reporting whatever comes back.
"""

from __future__ import annotations

import re
from typing import Final

_VERSION_RE: Final = re.compile(r"\d+")
_SPEC_RE: Final = re.compile(r"^(?P<op>>=|<=|>|<|==)?\s*(?P<version>[\w.]+)$")
_RANGE_RE: Final = re.compile(r"^(?P<low>[\w.]+)\s*-\s*(?P<high>[\w.]+)$")

#: A spec of "*" (or nothing at all) means the method is not firmware-limited.
ANY_FIRMWARE: Final = "*"


def parse_version(text: str | None) -> tuple[int, ...] | None:
    """Turn a firmware string into comparable numbers.

    ``"1.40"`` becomes ``(1, 40)`` and ``"Ver.1.03"`` becomes ``(1, 3)``. A
    string with no digits at all has no version.
    """
    if not text:
        return None
    numbers = _VERSION_RE.findall(text)
    if not numbers:
        return None
    return tuple(int(part) for part in numbers)


def _pad(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    width = max(len(left), len(right))
    return (
        left + (0,) * (width - len(left)),
        right + (0,) * (width - len(right)),
    )


def firmware_matches(spec: str | None, firmware: str | None) -> bool:
    """Does ``firmware`` fall inside ``spec``?

    Supported specs: ``*``, ``1.40``, ``>=1.30``, ``<=2.00``, ``>1.0``,
    ``<2.0``, and ``1.30-2.00``. Anything else returns False.
    """
    if spec is None or spec.strip() in {"", ANY_FIRMWARE}:
        return True

    version = parse_version(firmware)
    if version is None:
        return False

    text = spec.strip()

    range_match = _RANGE_RE.match(text)
    if range_match:
        low = parse_version(range_match.group("low"))
        high = parse_version(range_match.group("high"))
        if low is None or high is None:
            return False
        left, right = _pad(version, low)
        if left < right:
            return False
        left, right = _pad(version, high)
        return left <= right

    spec_match = _SPEC_RE.match(text)
    if not spec_match:
        return False
    target = parse_version(spec_match.group("version"))
    if target is None:
        return False

    left, right = _pad(version, target)
    operator = spec_match.group("op") or "=="
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    return left == right
