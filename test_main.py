"""API behaviour must match Assignment 1, plus data must survive a restart.

Each test gets its own throwaway database file. Run: pytest -q
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DB", str(tmp_path / "test.db"))
    import db
    import main

    importlib.reload(db)  # pick up the new TASKS_DB path
    importlib.reload(main)
    return main


@pytest.fixture()
def client(app_module):
    with TestClient(app_module.app) as c:  # "with" runs startup, which creates the DB
        yield c


def test_database_file_is_created_and_seeded_once(tmp_path, app_module):
    with TestClient(app_module.app) as c:
        assert len(c.get("/tasks").json()) == 3
    assert (tmp_path / "test.db").exists()
    with TestClient(app_module.app) as c:  # second "run" of the server
        assert len(c.get("/tasks").json()) == 3  # not 6


def test_data_survives_restart(app_module):
    with TestClient(app_module.app) as c:
        c.post("/tasks", json={"title": "Buy milk"})
    with TestClient(app_module.app) as c:
        assert [t["title"] for t in c.get("/tasks").json()][-1] == "Buy milk"


def test_read(client):
    assert client.get("/tasks/1").json()["id"] == 1
    r = client.get("/tasks/99")
    assert r.status_code == 404 and r.json() == {"error": "Task 99 not found"}
    assert client.get("/tasks/abc").status_code == 400


def test_create(client):
    r = client.post("/tasks", json={"title": "  Buy milk  "})
    assert r.status_code == 201
    body = r.json()
    assert (body["id"], body["title"], body["done"]) == (4, "Buy milk", False)
    assert body["created_at"] and body["updated_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 123}])
def test_create_rejects_bad_title(client, body):
    r = client.post("/tasks", json=body)
    assert r.status_code == 400 and "error" in r.json()


def test_update_and_delete(client):
    assert client.put("/tasks/2", json={"done": True}).json()["done"] is True
    assert client.put("/tasks/2", json={"title": "Renamed"}).json()["title"] == "Renamed"
    assert client.put("/tasks/99", json={"done": True}).status_code == 404
    assert client.put("/tasks/2", json={}).status_code == 400
    assert client.delete("/tasks/2").status_code == 204
    assert client.get("/tasks/2").status_code == 404
    assert client.delete("/tasks/2").status_code == 404


def test_sql_filters_and_stats(client):
    assert [t["id"] for t in client.get("/tasks?done=true").json()] == [1]
    assert [t["id"] for t in client.get("/tasks?search=GITHUB").json()] == [3]
    assert client.get("/tasks?search=%25").json() == []  # "%" is matched literally, not as a wildcard
    assert client.get("/stats").json() == {"total": 3, "done": 1, "open": 2}


def test_reset(client):
    client.post("/tasks", json={"title": "Extra"})
    assert [t["id"] for t in client.post("/reset").json()] == [1, 2, 3]
