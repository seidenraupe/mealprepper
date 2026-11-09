"""SQLite-Speicher für Vorrat, Rezepte und den manuellen Menüplan."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from season import (
    MONTHS_DE,
    STARTER_INGREDIENTS,
    WEEKDAYS_DE,
    format_season,
    ingredient_availability,
    months_to_storage,
    parse_months,
    recipe_cookable,
)

MEALS = ("lunch", "dinner")
MEAL_LABELS = {"lunch": "Mittag", "dinner": "Abend"}
MAX_NAME = 80
MAX_UNIT = 24
MAX_TITLE = 160
MAX_STEPS = 4000
MAX_PEOPLE = 99
MAX_SERVINGS = 99
MAX_QUANTITY = 1_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    unit TEXT NOT NULL DEFAULT '',
    season_months TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pantry_items (
    ingredient_id INTEGER PRIMARY KEY,
    quantity REAL NOT NULL,
    best_before TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    servings INTEGER NOT NULL DEFAULT 2,
    steps TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    PRIMARY KEY (recipe_id, ingredient_id),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
);

CREATE TABLE IF NOT EXISTS meal_plans (
    day TEXT NOT NULL,
    meal TEXT NOT NULL CHECK (meal IN ('lunch', 'dinner')),
    recipe_id INTEGER,
    people INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source = 'manual'),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (day, meal),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE SET NULL
);
"""


class DomainError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def open_db(db_path: Path):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with open_db(db_path) as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) AS n FROM ingredients").fetchone()["n"]
        if count == 0:
            conn.executemany(
                "INSERT INTO ingredients (name, unit, season_months) VALUES (?, ?, ?)",
                [
                    (name, unit, months_to_storage(list(months)))
                    for name, unit, months in STARTER_INGREDIENTS
                ],
            )


def require_month(month: int) -> int:
    if month < 1 or month > 12:
        raise DomainError("Monat muss zwischen 1 und 12 liegen.")
    return month


def parse_day(value) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise DomainError("Datum muss JJJJ-MM-TT sein.") from exc


def parse_optional_day(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return parse_day(text).isoformat()


def parse_quantity(value) -> float:
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DomainError("Menge muss eine Zahl sein.") from exc
    if number < 0 or number > MAX_QUANTITY:
        raise DomainError("Menge ist ungültig.")
    return number


def parse_positive_int(value, label: str, upper: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DomainError(f"{label} muss eine ganze Zahl sein.") from exc
    if number < 1 or number > upper:
        raise DomainError(f"{label} muss zwischen 1 und {upper} liegen.")
    return number


def clean_name(value, label: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise DomainError(f"{label} fehlt.")
    if len(text) > limit:
        raise DomainError(f"{label} darf höchstens {limit} Zeichen haben.")
    return text


def clean_unit(value) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > MAX_UNIT:
        raise DomainError(f"Einheit darf höchstens {MAX_UNIT} Zeichen haben.")
    return text


def clean_steps(value) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    if len(text) > MAX_STEPS:
        raise DomainError(f"Schritte dürfen höchstens {MAX_STEPS} Zeichen haben.")
    return text


def months_from(value) -> list[int]:
    try:
        return parse_months(value)
    except ValueError as exc:
        raise DomainError(str(exc)) from exc


def _ingredient_payload(row, month: int) -> dict:
    months = parse_months(row["season_months"])
    pantry_quantity = float(row["pantry_quantity"] or 0)
    best_before = row["best_before"] or ""
    payload = {
        "id": row["id"],
        "name": row["name"],
        "unit": row["unit"],
        "season_months": months,
        "season_label": format_season(months),
        "pantry_quantity": pantry_quantity,
        "best_before": best_before,
    }
    payload.update(ingredient_availability(months, pantry_quantity, month))
    return payload


def list_ingredients(db_path: Path, month: int) -> list[dict]:
    require_month(month)
    with open_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.name, i.unit, i.season_months,
                   COALESCE(p.quantity, 0) AS pantry_quantity,
                   p.best_before
            FROM ingredients i
            LEFT JOIN pantry_items p ON p.ingredient_id = i.id
            ORDER BY i.name COLLATE NOCASE
            """
        ).fetchall()
    return [_ingredient_payload(row, month) for row in rows]


def add_ingredient(db_path: Path, name, unit, season_months, month: int) -> dict:
    require_month(month)
    cleaned = clean_name(name, "Name", MAX_NAME)
    stored_unit = clean_unit(unit)
    months = months_from(season_months)
    try:
        with open_db(db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO ingredients (name, unit, season_months) VALUES (?, ?, ?)",
                (cleaned, stored_unit, months_to_storage(months)),
            )
            ingredient_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        raise DomainError("Diese Zutat gibt es schon.") from exc
    return get_ingredient(db_path, ingredient_id, month)


def update_ingredient(db_path: Path, ingredient_id: int, name, unit, season_months, month: int) -> dict:
    require_month(month)
    cleaned = clean_name(name, "Name", MAX_NAME)
    stored_unit = clean_unit(unit)
    months = months_from(season_months)
    try:
        with open_db(db_path) as conn:
            exists = conn.execute(
                "SELECT id FROM ingredients WHERE id = ?",
                (ingredient_id,),
            ).fetchone()
            if exists is None:
                raise DomainError("Zutat nicht gefunden.", 404)
            conn.execute(
                """
                UPDATE ingredients
                SET name = ?, unit = ?, season_months = ?
                WHERE id = ?
                """,
                (cleaned, stored_unit, months_to_storage(months), ingredient_id),
            )
    except sqlite3.IntegrityError as exc:
        raise DomainError("Diese Zutat gibt es schon.") from exc
    return get_ingredient(db_path, ingredient_id, month)


def get_ingredient(db_path: Path, ingredient_id: int, month: int) -> dict:
    require_month(month)
    with open_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT i.id, i.name, i.unit, i.season_months,
                   COALESCE(p.quantity, 0) AS pantry_quantity,
                   p.best_before
            FROM ingredients i
            LEFT JOIN pantry_items p ON p.ingredient_id = i.id
            WHERE i.id = ?
            """,
            (ingredient_id,),
        ).fetchone()
    if row is None:
        raise DomainError("Zutat nicht gefunden.", 404)
    return _ingredient_payload(row, month)


def delete_ingredient(db_path: Path, ingredient_id: int) -> None:
    with open_db(db_path) as conn:
        used = conn.execute(
            "SELECT 1 FROM recipe_ingredients WHERE ingredient_id = ?",
            (ingredient_id,),
        ).fetchone()
        if used is not None:
            raise DomainError("Diese Zutat steckt in einem Rezept.", 409)
        cursor = conn.execute("DELETE FROM ingredients WHERE id = ?", (ingredient_id,))
        if cursor.rowcount == 0:
            raise DomainError("Zutat nicht gefunden.", 404)


def set_pantry(db_path: Path, ingredient_id: int, quantity, best_before, month: int) -> dict:
    require_month(month)
    amount = parse_quantity(quantity)
    best = parse_optional_day(best_before)
    with open_db(db_path) as conn:
        exists = conn.execute(
            "SELECT id FROM ingredients WHERE id = ?",
            (ingredient_id,),
        ).fetchone()
        if exists is None:
            raise DomainError("Zutat nicht gefunden.", 404)
        conn.execute(
            """
            INSERT INTO pantry_items (ingredient_id, quantity, best_before, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ingredient_id) DO UPDATE SET
                quantity = excluded.quantity,
                best_before = excluded.best_before,
                updated_at = CURRENT_TIMESTAMP
            """,
            (ingredient_id, amount, best),
        )
    return get_ingredient(db_path, ingredient_id, month)


def _recipe_lines(conn, month: int) -> dict[int, list[dict]]:
    rows = conn.execute(
        """
        SELECT ri.recipe_id, ri.quantity AS amount,
               i.id, i.name, i.unit, i.season_months,
               COALESCE(p.quantity, 0) AS pantry_quantity,
               p.best_before
        FROM recipe_ingredients ri
        JOIN ingredients i ON i.id = ri.ingredient_id
        LEFT JOIN pantry_items p ON p.ingredient_id = i.id
        ORDER BY i.name COLLATE NOCASE
        """
    ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        payload = _ingredient_payload(row, month)
        payload["amount"] = float(row["amount"])
        grouped.setdefault(row["recipe_id"], []).append(payload)
    return grouped


def _recipe_payload(row, lines: list[dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "servings": row["servings"],
        "steps": row["steps"],
        "ingredients": lines,
        "cookable": recipe_cookable(lines),
    }


def list_recipes(db_path: Path, month: int) -> list[dict]:
    require_month(month)
    with open_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, title, servings, steps FROM recipes ORDER BY title COLLATE NOCASE"
        ).fetchall()
        lines = _recipe_lines(conn, month)
    return [_recipe_payload(row, lines.get(row["id"], [])) for row in rows]


def _normalize_lines(conn, ingredients) -> list[tuple[int, float]]:
    if ingredients is None:
        ingredients = []
    if not isinstance(ingredients, list):
        raise DomainError("Zutaten müssen eine Liste sein.")
    lines: list[tuple[int, float]] = []
    seen: set[int] = set()
    for item in ingredients:
        if not isinstance(item, dict):
            raise DomainError("Jede Zutat braucht eine Menge.")
        try:
            ingredient_id = int(item.get("ingredient_id"))
        except (TypeError, ValueError) as exc:
            raise DomainError("Zutat fehlt.") from exc
        if ingredient_id in seen:
            raise DomainError("Dieselbe Zutat steht doppelt im Rezept.")
        seen.add(ingredient_id)
        amount = parse_quantity(item.get("quantity"))
        if amount <= 0:
            raise DomainError("Die Menge im Rezept muss grösser als 0 sein.")
        exists = conn.execute(
            "SELECT id FROM ingredients WHERE id = ?",
            (ingredient_id,),
        ).fetchone()
        if exists is None:
            raise DomainError("Zutat nicht gefunden.", 404)
        lines.append((ingredient_id, amount))
    return lines


def _write_lines(conn, recipe_id: int, lines: list[tuple[int, float]]) -> None:
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    conn.executemany(
        """
        INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity)
        VALUES (?, ?, ?)
        """,
        [(recipe_id, ingredient_id, amount) for ingredient_id, amount in lines],
    )


def add_recipe(db_path: Path, title, servings, steps, ingredients, month: int) -> dict:
    require_month(month)
    cleaned = clean_name(title, "Titel", MAX_TITLE)
    portion = parse_positive_int(servings if servings is not None else 2, "Portionen", MAX_SERVINGS)
    stored_steps = clean_steps(steps)
    with open_db(db_path) as conn:
        lines = _normalize_lines(conn, ingredients)
        cursor = conn.execute(
            """
            INSERT INTO recipes (title, servings, steps)
            VALUES (?, ?, ?)
            """,
            (cleaned, portion, stored_steps),
        )
        recipe_id = cursor.lastrowid
        _write_lines(conn, recipe_id, lines)
    return get_recipe(db_path, recipe_id, month)


def update_recipe(db_path: Path, recipe_id: int, title, servings, steps, ingredients, month: int) -> dict:
    require_month(month)
    cleaned = clean_name(title, "Titel", MAX_TITLE)
    portion = parse_positive_int(servings if servings is not None else 2, "Portionen", MAX_SERVINGS)
    stored_steps = clean_steps(steps)
    with open_db(db_path) as conn:
        exists = conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if exists is None:
            raise DomainError("Rezept nicht gefunden.", 404)
        lines = _normalize_lines(conn, ingredients)
        conn.execute(
            """
            UPDATE recipes
            SET title = ?, servings = ?, steps = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (cleaned, portion, stored_steps, recipe_id),
        )
        _write_lines(conn, recipe_id, lines)
    return get_recipe(db_path, recipe_id, month)


def get_recipe(db_path: Path, recipe_id: int, month: int) -> dict:
    require_month(month)
    with open_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, title, servings, steps FROM recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()
        if row is None:
            raise DomainError("Rezept nicht gefunden.", 404)
        lines = _recipe_lines(conn, month).get(recipe_id, [])
    return _recipe_payload(row, lines)


def delete_recipe(db_path: Path, recipe_id: int) -> None:
    with open_db(db_path) as conn:
        cursor = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        if cursor.rowcount == 0:
            raise DomainError("Rezept nicht gefunden.", 404)


def plan_dates(start: date, days: int) -> list[date]:
    count = parse_positive_int(days, "Tage", 14)
    return [start + timedelta(days=offset) for offset in range(count)]


def list_plan(db_path: Path, start: date, days: int, month: int) -> dict:
    require_month(month)
    dates = plan_dates(start, days)
    with open_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT mp.day, mp.meal, mp.recipe_id, mp.people, mp.source, r.title
            FROM meal_plans mp
            LEFT JOIN recipes r ON r.id = mp.recipe_id
            WHERE mp.day >= ? AND mp.day <= ?
            """,
            (dates[0].isoformat(), dates[-1].isoformat()),
        ).fetchall()
        lines = _recipe_lines(conn, month)
        recipes = {
            row["id"]: _recipe_payload(row, lines.get(row["id"], []))
            for row in conn.execute("SELECT id, title, servings, steps FROM recipes").fetchall()
        }
    by_key = {(row["day"], row["meal"]): row for row in rows}
    day_payloads = []
    for day in dates:
        meals = {}
        for meal in MEALS:
            row = by_key.get((day.isoformat(), meal))
            if row is None or row["recipe_id"] is None:
                meals[meal] = None
                continue
            recipe = recipes.get(row["recipe_id"])
            meals[meal] = {
                "recipe_id": row["recipe_id"],
                "recipe_title": row["title"] or "",
                "people": row["people"],
                "source": row["source"],
                "cookable": bool(recipe["cookable"]) if recipe else False,
            }
        day_payloads.append(
            {
                "date": day.isoformat(),
                "weekday": WEEKDAYS_DE[day.weekday()],
                "meals": meals,
            }
        )
    return {
        "start": dates[0].isoformat(),
        "end": dates[-1].isoformat(),
        "days": day_payloads,
    }


def set_plan(db_path: Path, day_value, meal, recipe_id, people, month: int) -> dict:
    require_month(month)
    day = parse_day(day_value)
    if meal not in MEALS:
        raise DomainError("Mahlzeit muss Mittag oder Abend sein.")
    try:
        chosen = int(recipe_id)
    except (TypeError, ValueError) as exc:
        raise DomainError("Rezept fehlt.") from exc
    portion = parse_positive_int(people, "Personen", MAX_PEOPLE)
    with open_db(db_path) as conn:
        recipe = conn.execute("SELECT id FROM recipes WHERE id = ?", (chosen,)).fetchone()
        if recipe is None:
            raise DomainError("Rezept nicht gefunden.", 404)
        conn.execute(
            """
            INSERT INTO meal_plans (day, meal, recipe_id, people, source, updated_at)
            VALUES (?, ?, ?, ?, 'manual', CURRENT_TIMESTAMP)
            ON CONFLICT(day, meal) DO UPDATE SET
                recipe_id = excluded.recipe_id,
                people = excluded.people,
                source = 'manual',
                updated_at = CURRENT_TIMESTAMP
            """,
            (day.isoformat(), meal, chosen, portion),
        )
    return list_plan(db_path, day, 1, month)["days"][0]


def clear_plan(db_path: Path, day_value, meal) -> None:
    day = parse_day(day_value)
    if meal not in MEALS:
        raise DomainError("Mahlzeit muss Mittag oder Abend sein.")
    with open_db(db_path) as conn:
        conn.execute(
            "DELETE FROM meal_plans WHERE day = ? AND meal = ?",
            (day.isoformat(), meal),
        )


def board(
    db_path: Path,
    start: date,
    days: int,
    month: int,
    default_people: int,
    default_days: int,
    today: date,
) -> dict:
    plan = list_plan(db_path, start, days, month)
    return {
        "today": today.isoformat(),
        "month": month,
        "month_label": MONTHS_DE[month - 1],
        "default_people": default_people,
        "default_days": default_days,
        "start": plan["start"],
        "end": plan["end"],
        "ingredients": list_ingredients(db_path, month),
        "recipes": list_recipes(db_path, month),
        "days": plan["days"],
    }
