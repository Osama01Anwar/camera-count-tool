"""Light and dark palettes.

Both are designed, not one derived from the other by inversion. Colour is used
for legibility and never to imply a measurement: there is no green "good" or
red "bad" shutter count, because a count is not a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class Palette:
    """One theme's colours."""

    window: str
    panel: str
    panel_border: str
    ink: str
    muted: str
    accent: str
    found: str
    absent: str
    field: str

    def stylesheet(self) -> str:
        return f"""
        QWidget {{
            background: {self.window};
            color: {self.ink};
            font-family: "Segoe UI", system-ui, sans-serif;
            font-size: 14px;
        }}
        QLabel#title {{ font-size: 20px; font-weight: 600; }}
        QLabel#subtitle {{ color: {self.muted}; font-size: 13px; }}
        QLabel#sectionHeading {{
            color: {self.muted};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1.2px;
        }}
        QLabel#headline {{ font-size: 17px; font-weight: 700; letter-spacing: 0.5px; }}
        QLabel#headlineFound {{ color: {self.found}; }}
        QLabel#headlineAbsent {{ color: {self.absent}; }}
        QLabel#countValue {{ font-size: 46px; font-weight: 700; }}
        QLabel#countAbsent {{ font-size: 26px; font-weight: 600; color: {self.muted}; }}
        QLabel#meta {{ color: {self.muted}; font-size: 12px; }}
        QLabel#fieldLabel {{ color: {self.muted}; }}
        QLabel#fieldValue {{ font-weight: 600; }}
        QFrame#panel {{
            background: {self.panel};
            border: 1px solid {self.panel_border};
            border-radius: 8px;
        }}
        QPushButton {{
            background: {self.field};
            border: 1px solid {self.panel_border};
            border-radius: 6px;
            padding: 9px 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {self.accent}; }}
        QPushButton:focus {{ border: 2px solid {self.accent}; outline: none; }}
        QPushButton:pressed {{ background: {self.panel_border}; }}
        QPushButton:disabled {{ color: {self.muted}; }}
        QPlainTextEdit, QTextEdit {{
            background: {self.field};
            border: 1px solid {self.panel_border};
            border-radius: 6px;
            font-family: Consolas, "Courier New", monospace;
            font-size: 12px;
        }}
        QStatusBar {{ color: {self.muted}; }}
        """


LIGHT = Palette(
    window="#f4f5f7",
    panel="#ffffff",
    panel_border="#d7dbe3",
    ink="#16181d",
    muted="#5b6270",
    accent="#2b5bd7",
    found="#0f5132",
    absent="#5b6270",
    field="#ffffff",
)

DARK = Palette(
    window="#15171c",
    panel="#1d2027",
    panel_border="#2f343d",
    ink="#e8eaee",
    muted="#98a0ae",
    accent="#6b9bff",
    found="#7ee2a8",
    absent="#98a0ae",
    field="#22262e",
)

PALETTES: dict[Theme, Palette] = {Theme.LIGHT: LIGHT, Theme.DARK: DARK}


def palette_for(theme: Theme) -> Palette:
    return PALETTES[theme]
