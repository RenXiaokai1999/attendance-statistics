from __future__ import annotations

import unicodedata
from datetime import date


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return "".join(
        character
        for character in normalized
        if not character.isspace() and unicodedata.category(character) != "Cf"
    )


def is_in_month(day: date, year: int, month: int) -> bool:
    return day.year == year and day.month == month

