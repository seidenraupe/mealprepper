from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "mealprepper" / "www"


@pytest.fixture
def client(tmp_path):
    from main import create_app

    app = create_app(data_dir=tmp_path, www_dir=WWW)
    return app.test_client()


@pytest.fixture
def ingredient(client):
    def find(name: str, month: int = 1) -> dict:
        payload = client.get(f"/api/board?month={month}").get_json()
        return next(item for item in payload["ingredients"] if item["name"] == name)

    return find
