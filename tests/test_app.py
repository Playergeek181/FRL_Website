import io

import pytest

from frl.app import create_app


@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path).test_client()


def test_state_empty(client):
    s = client.get("/api/state").get_json()
    assert s["phase"] == 1 and s["phase_name"] == "Localização e Mapeamento"
    assert s["current"] is None and s["ranking"] == []


def test_full_flow(client):
    a = client.post("/api/teams", data={"name": "Falcon"}).get_json()["teams"][0]["id"]
    client.post("/api/orders/1", json={"team_ids": [a]})
    client.post("/api/timer/start")
    s = client.post("/api/attempts", json={"team_id": a, "phase": 1,
        "inputs": dict(bases=5, repeats=1, returned=True, open_hw=True)}).get_json()
    assert s["current"]["name"] == "Falcon" and s["timer"]["running"]
    assert s["ranking"][0]["phase_points"]["1"] == 25 and s["ranking"][0]["total"] == 25


def test_delete_best_attempt_falls_back(client):
    a = client.post("/api/teams", data={"name": "A"}).get_json()["teams"][0]["id"]
    def add(b): return client.post("/api/attempts", json={"team_id": a, "phase": 1,
        "inputs": dict(bases=b, repeats=0, returned=False, open_hw=False)}).get_json()
    add(2); s = add(5)
    best = max(s["attempts"], key=lambda x: x["points"])
    s = client.delete(f"/api/attempts/{best['id']}").get_json()
    assert max(x["points"] for x in s["attempts"]) == 40


def test_invalid_attempt_400(client):
    a = client.post("/api/teams", data={"name": "A"}).get_json()["teams"][0]["id"]
    r = client.post("/api/attempts", json={"team_id": a, "phase": 1,
        "inputs": dict(bases=9, repeats=0, returned=False, open_hw=False)})
    assert r.status_code == 400 and r.get_json()["errors"]


def test_preview(client):
    r = client.post("/api/preview", json={"phase": 2,
        "inputs": dict(lifted=3, delivered=3, dropped=0, returned=True, open_hw=True)})
    assert r.get_json() == {"points": 720}


def test_logo_rejects_non_image(client):
    r = client.post("/api/teams", data={"name": "<b>X</b>",
        "logo": (io.BytesIO(b"x"), "evil.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert client.get("/api/state").get_json()["teams"] == []


def test_logo_upload_served(client):
    s = client.post("/api/teams", data={"name": "A",
        "logo": (io.BytesIO(b"\x89PNG"), "a.png")}, content_type="multipart/form-data").get_json()
    url = s["teams"][0]["logo"]
    assert url.startswith("/logos/") and client.get(url).status_code == 200


def test_pages(client):
    assert client.get("/").status_code == 302
    assert client.get("/tv").status_code == 200 and client.get("/controle").status_code == 200


def test_not_found_and_bad_body(client):
    r = client.delete("/api/teams/nope")
    assert r.status_code == 404 and r.get_json()["errors"]
    r = client.post("/api/phase", data="not json", content_type="application/json")
    assert r.status_code == 400
    assert client.post("/api/orders/1", json={"team_ids": "x"}).status_code == 400
