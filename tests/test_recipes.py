def _recipe(client, title, ingredient_ids, month=1):
    response = client.post(
        f"/api/recipes?month={month}",
        json={
            "title": title,
            "servings": 2,
            "steps": "Kochen",
            "ingredients": [{"ingredient_id": item_id, "quantity": 100} for item_id in ingredient_ids],
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_recipe_is_cookable_when_each_ingredient_is_seasonal_or_stocked(client, ingredient):
    spargel = ingredient("Spargel")
    reis = ingredient("Reis")
    recipe = _recipe(client, "Spargel mit Reis", [spargel["id"], reis["id"]])
    assert recipe["cookable"] is False

    stored = client.put(
        "/api/pantry?month=1",
        json={"ingredient_id": spargel["id"], "quantity": 200},
    )
    assert stored.status_code == 200
    again = client.get("/api/board?month=1").get_json()
    saved = next(item for item in again["recipes"] if item["id"] == recipe["id"])
    assert saved["cookable"] is True

    may = client.get("/api/board?month=5").get_json()
    in_may = next(item for item in may["recipes"] if item["id"] == recipe["id"])
    assert in_may["cookable"] is True


def test_empty_recipe_is_cookable_and_used_ingredient_stays(client, ingredient):
    created = client.post("/api/recipes?month=1", json={"title": "Tee", "servings": 1, "steps": ""})
    assert created.status_code == 201
    assert created.get_json()["cookable"] is True

    reis = ingredient("Reis")
    _recipe(client, "Reis pur", [reis["id"]])
    blocked = client.delete(f"/api/ingredients/{reis['id']}")
    assert blocked.status_code == 409


def test_duplicate_line_and_missing_title_fail(client, ingredient):
    reis = ingredient("Reis")
    duplicate = client.post(
        "/api/recipes",
        json={
            "title": "Doppelt",
            "servings": 2,
            "ingredients": [
                {"ingredient_id": reis["id"], "quantity": 1},
                {"ingredient_id": reis["id"], "quantity": 2},
            ],
        },
    )
    assert duplicate.status_code == 400
    missing = client.post("/api/recipes", json={"title": "  ", "servings": 2})
    assert missing.status_code == 400
