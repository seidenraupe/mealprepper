"""Mealprepper: Vorrat, Rezepte, Saison und manueller Menüplan."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory

import db
from db import DomainError

APP_VERSION = "0.1.0"
ZURICH = ZoneInfo("Europe/Zurich")
LISTEN_HOST = "0.0.0.0"


def zurich_today():
    return datetime.now(ZURICH).date()


def clamp_int(value, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(high, max(low, number))


def load_options(path: Path) -> dict:
    options = {
        "cloudflare_tunnel_token": "",
        "default_people": clamp_int(os.getenv("MEALPREPPER_DEFAULT_PEOPLE", "4"), 4, 1, 99),
        "default_days": clamp_int(os.getenv("MEALPREPPER_DEFAULT_DAYS", "7"), 7, 1, 14),
    }
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            options.update(loaded)
    options["default_people"] = clamp_int(options.get("default_people"), 4, 1, 99)
    options["default_days"] = clamp_int(options.get("default_days"), 7, 1, 14)
    options.pop("cloudflare_tunnel_token", None)
    return options


def create_app(data_dir: Path | None = None, www_dir: Path | None = None) -> Flask:
    data = Path(data_dir or os.getenv("MEALPREPPER_DATA_DIR", "/data"))
    www = Path(www_dir or os.getenv("MEALPREPPER_WWW_DIR", Path(__file__).resolve().parent / "www"))
    db_path = data / "mealprepper.db"
    options = load_options(data / "options.json")
    db.init_db(db_path)

    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    app.config["WWW"] = www
    app.config["OPTIONS"] = options

    @app.errorhandler(DomainError)
    def on_domain(error: DomainError):
        return jsonify({"error": error.message}), error.status

    @app.get("/api/health")
    def health():
        return jsonify({"service": "mealprepper", "ok": True, "version": APP_VERSION})

    @app.get("/api/board")
    def get_board():
        start, days, month = _board_query()
        return jsonify(
            db.board(
                app.config["DB_PATH"],
                start,
                days,
                month,
                app.config["OPTIONS"]["default_people"],
                app.config["OPTIONS"]["default_days"],
                zurich_today(),
            )
        )

    @app.post("/api/ingredients")
    def post_ingredient():
        payload = _body()
        month = _month_from(payload)
        return jsonify(
            db.add_ingredient(
                app.config["DB_PATH"],
                payload.get("name"),
                payload.get("unit"),
                payload.get("season_months"),
                month,
            )
        ), 201

    @app.patch("/api/ingredients/<int:ingredient_id>")
    def patch_ingredient(ingredient_id: int):
        payload = _body()
        month = _month_from(payload)
        return jsonify(
            db.update_ingredient(
                app.config["DB_PATH"],
                ingredient_id,
                payload.get("name"),
                payload.get("unit"),
                payload.get("season_months"),
                month,
            )
        )

    @app.delete("/api/ingredients/<int:ingredient_id>")
    def remove_ingredient(ingredient_id: int):
        db.delete_ingredient(app.config["DB_PATH"], ingredient_id)
        return jsonify({"ok": True})

    @app.put("/api/pantry")
    def put_pantry():
        payload = _body()
        try:
            ingredient_id = int(payload.get("ingredient_id"))
        except (TypeError, ValueError) as exc:
            raise DomainError("Zutat fehlt.") from exc
        month = _month_from(payload)
        return jsonify(
            db.set_pantry(
                app.config["DB_PATH"],
                ingredient_id,
                payload.get("quantity"),
                payload.get("best_before"),
                month,
            )
        )

    @app.post("/api/recipes")
    def post_recipe():
        payload = _body()
        month = _month_from(payload)
        return jsonify(
            db.add_recipe(
                app.config["DB_PATH"],
                payload.get("title"),
                payload.get("servings"),
                payload.get("steps"),
                payload.get("ingredients"),
                month,
            )
        ), 201

    @app.put("/api/recipes/<int:recipe_id>")
    def put_recipe(recipe_id: int):
        payload = _body()
        month = _month_from(payload)
        return jsonify(
            db.update_recipe(
                app.config["DB_PATH"],
                recipe_id,
                payload.get("title"),
                payload.get("servings"),
                payload.get("steps"),
                payload.get("ingredients"),
                month,
            )
        )

    @app.delete("/api/recipes/<int:recipe_id>")
    def remove_recipe(recipe_id: int):
        db.delete_recipe(app.config["DB_PATH"], recipe_id)
        return jsonify({"ok": True})

    @app.put("/api/plans")
    def put_plan():
        payload = _body()
        month = _month_from(payload)
        return jsonify(
            db.set_plan(
                app.config["DB_PATH"],
                payload.get("day"),
                payload.get("meal"),
                payload.get("recipe_id"),
                payload.get("people"),
                month,
            )
        )

    @app.delete("/api/plans")
    def remove_plan():
        payload = _body()
        db.clear_plan(app.config["DB_PATH"], payload.get("day"), payload.get("meal"))
        return jsonify({"ok": True})

    @app.get("/")
    def index():
        return send_from_directory(app.config["WWW"], "index.html")

    @app.get("/style.css")
    def style():
        return send_from_directory(app.config["WWW"], "style.css")

    @app.get("/app.js")
    def script():
        return send_from_directory(app.config["WWW"], "app.js")

    def _body() -> dict:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise DomainError("JSON-Objekt erwartet.")
        return payload

    def _month_from(payload: dict | None = None) -> int:
        raw = request.args.get("month")
        if raw is None and payload is not None:
            raw = payload.get("month")
        if raw is None or raw == "":
            return zurich_today().month
        return _plain_month(raw)

    def _plain_month(raw) -> int:
        try:
            month = int(raw)
        except (TypeError, ValueError) as exc:
            raise DomainError("Monat muss zwischen 1 und 12 liegen.") from exc
        return db.require_month(month)

    def _board_query():
        options = app.config["OPTIONS"]
        raw_start = request.args.get("start")
        start = db.parse_day(raw_start) if raw_start else zurich_today()
        raw_days = request.args.get("days")
        days = options["default_days"] if raw_days in (None, "") else db.parse_positive_int(raw_days, "Tage", 14)
        raw_month = request.args.get("month")
        month = zurich_today().month if raw_month in (None, "") else _plain_month(raw_month)
        return start, days, month

    return app


def main() -> None:
    port = int(os.getenv("MEALPREPPER_API_PORT", "5050"))
    app = create_app()
    from waitress import serve

    print(f"[mealprepper] http://{LISTEN_HOST}:{port}", flush=True)
    serve(app, host=LISTEN_HOST, port=port)


if __name__ == "__main__":
    main()
