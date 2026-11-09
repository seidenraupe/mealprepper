import json
from pathlib import Path

from season import STARTER_INGREDIENTS

WWW = Path(__file__).resolve().parents[1] / "mealprepper" / "www"


def test_starter_list_and_spargel_season(client, ingredient):
    january = client.get("/api/board?month=1").get_json()
    assert len(january["ingredients"]) == len(STARTER_INGREDIENTS)
    spargel = ingredient("Spargel")
    reis = ingredient("Reis")
    assert spargel["in_season"] is False
    assert spargel["season_label"] == "Apr–Jun"
    assert reis["in_season"] is True
    assert reis["season_label"] == "ganzjährig"

    assert ingredient("Spargel", month=5)["in_season"] is True


def test_pantry_quantity_and_duplicate_name(client, ingredient):
    spargel = ingredient("Spargel")
    stored = client.put(
        "/api/pantry?month=1",
        json={"ingredient_id": spargel["id"], "quantity": "1,5", "best_before": "2026-12-01"},
    )
    assert stored.status_code == 200
    body = stored.get_json()
    assert body["pantry_quantity"] == 1.5
    assert body["best_before"] == "2026-12-01"
    assert body["in_pantry"] is True
    assert body["available"] is True

    created = client.post(
        "/api/ingredients?month=1",
        json={"name": "Spargel", "unit": "g", "season_months": [4, 5, 6]},
    )
    assert created.status_code == 400

    negative = client.put(
        "/api/pantry",
        json={"ingredient_id": spargel["id"], "quantity": -1},
    )
    assert negative.status_code == 400


def test_options_set_people_and_days_without_leaking_the_token(tmp_path):
    from main import create_app

    Path(tmp_path, "options.json").write_text(
        json.dumps(
            {
                "default_people": 2,
                "default_days": 3,
                "cloudflare_tunnel_token": "secret-token",
            }
        ),
        encoding="utf-8",
    )
    app = create_app(data_dir=tmp_path, www_dir=WWW)
    body = app.test_client().get("/api/board").get_json()
    assert body["default_people"] == 2
    assert body["default_days"] == 3
    assert len(body["days"]) == 3
    assert "secret-token" not in json.dumps(body)
