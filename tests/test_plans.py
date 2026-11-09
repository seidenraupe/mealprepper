def _recipe(client, title):
    response = client.post("/api/recipes", json={"title": title, "servings": 4, "steps": "Anrichten"})
    assert response.status_code == 201
    return response.get_json()


def test_manual_plan_can_be_set_changed_and_cleared(client):
    first = _recipe(client, "Linsensuppe")
    second = _recipe(client, "Ofengemüse")
    saved = client.put(
        "/api/plans?month=11",
        json={
            "day": "2026-11-09",
            "meal": "lunch",
            "recipe_id": first["id"],
            "people": 4,
            "source": "jetson",
        },
    )
    assert saved.status_code == 200
    slot = saved.get_json()["meals"]["lunch"]
    assert slot["recipe_id"] == first["id"]
    assert slot["people"] == 4
    assert slot["source"] == "manual"
    assert slot["cookable"] is True

    changed = client.put(
        "/api/plans",
        json={"day": "2026-11-09", "meal": "lunch", "recipe_id": second["id"], "people": 5},
    )
    assert changed.get_json()["meals"]["lunch"]["recipe_title"] == "Ofengemüse"
    assert changed.get_json()["meals"]["lunch"]["people"] == 5

    board = client.get("/api/board?start=2026-11-09&days=2").get_json()
    assert board["days"][0]["date"] == "2026-11-09"
    assert board["days"][0]["weekday"]
    assert board["days"][0]["meals"]["dinner"] is None
    assert board["days"][1]["date"] == "2026-11-10"

    cleared = client.delete("/api/plans", json={"day": "2026-11-09", "meal": "lunch"})
    assert cleared.status_code == 200
    after = client.get("/api/board?start=2026-11-09&days=1").get_json()
    assert after["days"][0]["meals"]["lunch"] is None


def test_invalid_plan_and_deleted_recipe_leave_the_slot_empty(client):
    recipe = _recipe(client, "Brotzeit")
    client.put(
        "/api/plans",
        json={"day": "2026-11-10", "meal": "dinner", "recipe_id": recipe["id"], "people": 2},
    )
    invalid = client.put(
        "/api/plans",
        json={"day": "2026-11-10", "meal": "breakfast", "recipe_id": recipe["id"], "people": 2},
    )
    assert invalid.status_code == 400
    too_long = client.get("/api/board?days=15")
    assert too_long.status_code == 400

    deleted = client.delete(f"/api/recipes/{recipe['id']}")
    assert deleted.status_code == 200
    board = client.get("/api/board?start=2026-11-10&days=1").get_json()
    assert board["days"][0]["meals"]["dinner"] is None


def test_health_and_page_shell(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["service"] == "mealprepper"
    assert health.get_json()["ok"] is True

    page = client.get("/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Vorrat" in html
    assert "Rezepte" in html
    assert "Plan" in html
    assert "Plan erstellen" not in html
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200
