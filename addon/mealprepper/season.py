"""Saisonregeln und die Startliste für einen Schweizer Haushalt."""

from __future__ import annotations

MONTHS_DE = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
MONTHS_SHORT_DE = (
    "Jan",
    "Feb",
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
)
WEEKDAYS_DE = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)

# name, unit, months. Leere Monate bedeuten ganzjährig.
STARTER_INGREDIENTS: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("Apfel", "Stk", (1, 2, 3, 8, 9, 10, 11, 12)),
    ("Aprikose", "Stk", (7, 8)),
    ("Aubergine", "Stk", (7, 8, 9)),
    ("Birne", "Stk", (8, 9, 10, 11)),
    ("Blumenkohl", "Stk", (6, 7, 8, 9, 10)),
    ("Bohne", "g", (7, 8, 9)),
    ("Broccoli", "g", (6, 7, 8, 9, 10)),
    ("Brombeere", "g", (8, 9)),
    ("Brot", "g", ()),
    ("Butter", "g", ()),
    ("Chicorée", "Stk", (1, 2, 3, 11, 12)),
    ("Ei", "Stk", ()),
    ("Erbse", "g", (6, 7)),
    ("Erdbeere", "g", (5, 6, 7)),
    ("Federkohl", "g", (1, 2, 10, 11, 12)),
    ("Gurke", "Stk", (6, 7, 8, 9)),
    ("Haferflocken", "g", ()),
    ("Heidelbeere", "g", (7, 8)),
    ("Himbeere", "g", (6, 7, 8)),
    ("Joghurt", "g", ()),
    ("Karotte", "Stk", ()),
    ("Kartoffel", "g", ()),
    ("Käse", "g", ()),
    ("Kichererbsen", "g", ()),
    ("Kirsche", "g", (6, 7)),
    ("Knoblauch", "Zehe", ()),
    ("Kohlrabi", "Stk", (5, 6, 7, 8, 9, 10)),
    ("Kopfsalat", "Stk", (5, 6, 7, 8, 9)),
    ("Kürbis", "g", (9, 10, 11, 12)),
    ("Lauch", "Stk", (1, 2, 3, 9, 10, 11, 12)),
    ("Linsen", "g", ()),
    ("Mais", "Stk", (8, 9)),
    ("Mehl", "g", ()),
    ("Milch", "ml", ()),
    ("Nüsslisalat", "g", (1, 2, 3, 10, 11, 12)),
    ("Öl", "EL", ()),
    ("Paprika", "Stk", (7, 8, 9)),
    ("Pastinake", "g", (1, 2, 3, 10, 11, 12)),
    ("Pilze", "g", (9, 10)),
    ("Quark", "g", ()),
    ("Quitte", "Stk", (10, 11)),
    ("Reis", "g", ()),
    ("Rhabarber", "g", (4, 5, 6)),
    ("Rosenkohl", "g", (1, 2, 10, 11, 12)),
    ("Salz", "Prise", ()),
    ("Sellerie", "Stk", (1, 2, 9, 10, 11, 12)),
    ("Spargel", "g", (4, 5, 6)),
    ("Spinat", "g", (4, 5, 6, 9, 10)),
    ("Teigwaren", "g", ()),
    ("Tomate", "Stk", (7, 8, 9)),
    ("Tomatenpüree", "g", ()),
    ("Traube", "g", (9, 10)),
    ("Wirz", "g", (1, 2, 3, 9, 10, 11, 12)),
    ("Zucker", "g", ()),
    ("Zucchini", "Stk", (6, 7, 8, 9)),
    ("Zwetschge", "g", (8, 9)),
    ("Zwiebel", "Stk", ()),
)


def parse_months(value) -> list[int]:
    """Leer bedeutet ganzjährig. Zwölf gesetzte Monate werden ebenfalls ganzjährig."""
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise ValueError("Saison muss eine Liste von Monaten sein.")
    months: list[int] = []
    for part in parts:
        try:
            month = int(part)
        except (TypeError, ValueError) as exc:
            raise ValueError("Saisonmonate müssen Zahlen von 1 bis 12 sein.") from exc
        if month < 1 or month > 12:
            raise ValueError("Saisonmonate müssen zwischen 1 und 12 liegen.")
        if month not in months:
            months.append(month)
    months.sort()
    if len(months) == 12:
        return []
    return months


def months_to_storage(months: list[int]) -> str:
    return ",".join(str(month) for month in months)


def in_season(months: list[int], month: int) -> bool:
    if not months:
        return True
    return month in months


def format_season(months: list[int]) -> str:
    if not months:
        return "ganzjährig"
    present = set(months)

    def previous_month(month: int) -> int:
        return 12 if month == 1 else month - 1

    def next_month(month: int) -> int:
        return 1 if month == 12 else month + 1

    parts: list[str] = []
    for start in months:
        if previous_month(start) in present:
            continue
        end = start
        while next_month(end) in present and next_month(end) != start:
            end = next_month(end)
        if start == end:
            parts.append(MONTHS_SHORT_DE[start - 1])
        else:
            parts.append(f"{MONTHS_SHORT_DE[start - 1]}–{MONTHS_SHORT_DE[end - 1]}")
    return ", ".join(parts)


def ingredient_availability(months: list[int], pantry_quantity: float, month: int) -> dict:
    seasonal = in_season(months, month)
    stocked = pantry_quantity > 0
    return {
        "in_season": seasonal,
        "in_pantry": stocked,
        "available": seasonal or stocked,
    }


def recipe_cookable(ingredients: list[dict]) -> bool:
    if not ingredients:
        return True
    return all(item["available"] for item in ingredients)
