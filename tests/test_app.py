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


def _mk(client, name):
    return client.post("/api/teams", data={"name": name}).get_json()["teams"][-1]["id"]


def _att(client, team, bases):
    return client.post("/api/attempts", json={"team_id": team, "phase": 1,
        "inputs": dict(bases=bases, repeats=0, returned=False, open_hw=False)}).get_json()


def _rank(s):
    return {r["team_id"]: r for r in s["ranking"]}


def test_delete_best_attempt_updates_ranking(client):
    a, b = _mk(client, "A"), _mk(client, "B")
    _att(client, a, 2)
    s = _att(client, a, 5)
    s = _att(client, b, 3)
    best = max((x for x in s["attempts"] if x["team_id"] == a), key=lambda x: x["points"])
    assert _rank(s)[a]["position"] == 1 and _rank(s)[a]["phase_points"]["1"] == 25
    s = client.delete(f"/api/attempts/{best['id']}").get_json()
    assert best["id"] not in [x["id"] for x in s["attempts"]]
    r = _rank(s)
    assert r[b]["position"] == 1 and r[b]["phase_points"]["1"] == 25 and r[b]["total"] == 25
    assert r[a]["position"] == 2 and r[a]["phase_points"]["1"] == 18 and r[a]["total"] == 18


def test_put_lowering_best_attempt_updates_ranking(client):
    a, b = _mk(client, "A"), _mk(client, "B")
    s = _att(client, a, 5)
    s = _att(client, b, 3)
    aid = next(x["id"] for x in s["attempts"] if x["team_id"] == a)
    assert _rank(s)[a]["position"] == 1
    s = client.put(f"/api/attempts/{aid}", json={"inputs": dict(
        bases=1, repeats=0, returned=False, open_hw=False)}).get_json()
    r = _rank(s)
    assert next(x for x in s["attempts"] if x["id"] == aid)["inputs"]["bases"] == 1
    assert r[b]["position"] == 1 and r[b]["total"] == 25
    assert r[a]["position"] == 2 and r[a]["phase_points"]["1"] == 18


def _logo_post(client, url, name, data=b"\x89PNG"):
    return client.post(url, data={"name": "A", "logo": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def test_logo_replace_removes_old_file(client, tmp_path):
    s = _logo_post(client, "/api/teams", "a.png").get_json()
    tid = s["teams"][0]["id"]
    assert (tmp_path / "logos" / f"{tid}.png").exists()
    s = _logo_post(client, f"/api/teams/{tid}", "b.jpg").get_json()
    assert s["teams"][0]["logo"] == f"/logos/{tid}.jpg"
    assert not (tmp_path / "logos" / f"{tid}.png").exists()
    assert (tmp_path / "logos" / f"{tid}.jpg").exists()


def test_team_delete_removes_logo_file(client, tmp_path):
    tid = _logo_post(client, "/api/teams", "a.png").get_json()["teams"][0]["id"]
    assert (tmp_path / "logos" / f"{tid}.png").exists()
    client.delete(f"/api/teams/{tid}")
    assert not list((tmp_path / "logos").glob(f"{tid}.*"))


def test_oversized_upload_413_json(client):
    r = _logo_post(client, "/api/teams", "a.png", data=b"0" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 413 and r.get_json()["errors"]
    assert client.get("/api/state").get_json()["teams"] == []


def test_open_hw_default_create_and_edit(client):
    s = client.post("/api/teams", data={"name": "A", "open_hw_default": "true"}).get_json()
    tid = s["teams"][0]["id"]
    assert s["teams"][0]["open_hw_default"] is True
    s = client.post("/api/teams", data={"name": "B"}).get_json()
    assert s["teams"][1]["open_hw_default"] is False
    s = client.post(f"/api/teams/{tid}", data={"open_hw_default": "false"}).get_json()
    assert s["teams"][0]["open_hw_default"] is False and s["teams"][0]["name"] == "A"
    s = client.post(f"/api/teams/{tid}", data={"open_hw_default": "1"}).get_json()
    assert s["teams"][0]["open_hw_default"] is True
    s = client.post(f"/api/teams/{tid}", data={"name": "Z"}).get_json()
    assert s["teams"][0]["name"] == "Z" and s["teams"][0]["open_hw_default"] is True
