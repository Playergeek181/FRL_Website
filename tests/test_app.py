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
    assert client.get("/").status_code == 200
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
    assert s["teams"][0]["logo"].startswith(f"/logos/{tid}.jpg?v=")
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


def test_static_assets_served(client):
    assert client.get("/static/tv.js").status_code == 200
    assert client.get("/static/tv.css").status_code == 200
    assert client.get("/static/common.css").status_code == 200
    assert client.get("/static/../app.py").status_code == 404


def test_ranking_positions_null_until_scored(client):
    a, b = _mk(client, "A"), _mk(client, "B")
    s = client.get("/api/state").get_json()
    assert [r["position"] for r in s["ranking"]] == [None, None]
    _att(client, b, 2)
    r = _rank(client.get("/api/state").get_json())
    assert r[b]["position"] == 1 and r[a]["position"] is None


def test_logo_url_changes_when_replaced_with_same_extension(client, tmp_path):
    import os
    s = _logo_post(client, "/api/teams", "a.png").get_json()
    tid = s["teams"][0]["id"]
    url1 = s["teams"][0]["logo"]
    assert url1.startswith(f"/logos/{tid}.png?v=")
    assert client.get(url1).status_code == 200
    path = tmp_path / "logos" / f"{tid}.png"
    st = path.stat()
    os.utime(path, (st.st_atime - 100, st.st_mtime - 100))   # simula upload antigo
    url_old = client.get("/api/state").get_json()["teams"][0]["logo"]
    s = _logo_post(client, f"/api/teams/{tid}", "b.png", data=b"\x89PNG2").get_json()
    url2 = s["teams"][0]["logo"]
    assert url2 != url_old and url2.startswith(f"/logos/{tid}.png?v=")
    assert s["ranking"][0]["logo"] == url2
    assert client.get(url2).data == b"\x89PNG2"


def test_preview_errors_name_fields(client):
    r = client.post("/api/preview", json={"phase": 1,
        "inputs": dict(bases=9, repeats=0, returned=False, open_hw=False)})
    assert r.status_code == 400
    assert r.get_json() == {"errors": ["Bases visitadas: no máximo 6."], "fields": ["bases"]}


def test_team_delete_can_be_undone_with_logo(client, tmp_path):
    tid = _logo_post(client, "/api/teams", "a.png").get_json()["teams"][0]["id"]
    client.post("/api/attempts", json={"team_id": tid, "phase": 1,
        "inputs": dict(bases=2, repeats=0, returned=False, open_hw=False)})
    client.delete(f"/api/teams/{tid}")
    s = client.post(f"/api/teams/{tid}/restore").get_json()
    assert s["teams"][0]["id"] == tid and len(s["attempts"]) == 1
    assert (tmp_path / "logos" / f"{tid}.png").exists()
    assert client.post(f"/api/teams/{tid}/restore").status_code == 400


def test_state_reports_time_up_and_slot_index(tmp_path):
    from frl.app import create_app
    app = create_app(tmp_path)
    c = app.test_client()
    a = c.post("/api/teams", data={"name": "A"}).get_json()["teams"][0]["id"]
    c.post("/api/orders/1", json={"team_ids": [a]})
    s = c.get("/api/state").get_json()
    assert s["slot_index"] == 0 and s["timer"]["expired"] is False


def test_undo_next_and_restore_attempt_routes(client):
    ids = [client.post("/api/teams", data={"name": n}).get_json()["teams"][-1]["id"] for n in ("A", "B")]
    client.post("/api/orders/1", json={"team_ids": ids})
    assert client.post("/api/timer/next").get_json()["current"]["id"] == ids[1]
    assert client.post("/api/timer/back").get_json()["current"]["id"] == ids[0]
    assert client.post("/api/timer/back").status_code == 400
    inputs = {"bases": 3, "repeats": 0, "returned": True, "open_hw": False}
    att = client.post("/api/attempts", json={"team_id": ids[0], "phase": 1, "inputs": inputs}).get_json()["attempts"][0]
    client.delete(f"/api/attempts/{att['id']}")
    s = client.post(f"/api/attempts/{att['id']}/restore").get_json()
    assert [a["id"] for a in s["attempts"]] == [att["id"]]


def test_phase_undo_route(client):
    assert client.post("/api/phase/undo").status_code == 400
    client.post("/api/phase", json={"phase": 2})
    assert client.post("/api/phase/undo").get_json()["phase"] == 1


@pytest.fixture
def secured(tmp_path):
    app = create_app(tmp_path, auth=("admin", "senha-forte-1"))
    return app.test_client(), tmp_path


def _login(c, u="admin", p="senha-forte-1"):
    return c.post("/login", data={"username": u, "password": p, "next": "/controle"})


def test_public_pages_and_state(secured):
    c, _ = secured
    assert c.get("/").status_code == 200
    assert c.get("/tv").status_code == 200
    assert c.get("/login").status_code == 200
    assert c.get("/api/state").status_code == 200
    assert c.get("/api/me").get_json()["user"] is None


def test_protected_requires_login(secured):
    c, _ = secured
    r = c.get("/controle")
    assert r.status_code == 302 and r.headers["Location"].startswith("/login?next=")
    assert c.post("/api/timer/start").status_code == 401
    assert c.post("/api/teams", data={"name": "X"}).status_code == 401
    assert c.get("/api/users").status_code == 401


def test_login_flow(secured):
    c, _ = secured
    r = _login(c, p="errada")
    assert "error=bad" in r.headers["Location"]
    r = _login(c)
    assert r.status_code == 302 and r.headers["Location"] == "/controle"
    assert c.get("/controle").status_code == 200
    assert c.post("/api/teams", data={"name": "X"}).status_code == 200
    assert c.get("/api/me").get_json()["user"]["username"] == "admin"
    c.post("/logout")
    assert c.get("/controle").status_code == 302


def test_open_redirect_blocked(secured):
    c, _ = secured
    r = c.post("/login", data={"username": "admin", "password": "senha-forte-1", "next": "https://evil.example"})
    assert r.headers["Location"] == "/controle"


def test_throttle_locks_after_failures(secured):
    c, _ = secured
    for _ in range(5):
        _login(c, p="x")
    r = _login(c)  # even the right password is refused while locked
    assert "error=locked" in r.headers["Location"]


def test_admin_creates_operator_who_cannot_manage_users(secured):
    c, _ = secured
    _login(c)
    r = c.post("/api/users", json={"username": "juiz1", "password": "outra-senha-9", "role": "operator"})
    assert r.status_code == 200
    assert {u["username"] for u in r.get_json()["users"]} == {"admin", "juiz1"}
    assert c.post("/api/users", json={"username": "juiz1", "password": "outra-senha-9"}).status_code == 400
    assert c.post("/api/users", json={"username": "x", "password": "curta"}).status_code == 400
    c.post("/logout")
    assert _login(c, "JUIZ1", "outra-senha-9").headers["Location"] == "/controle"  # case-insensitive name
    assert c.get("/controle").status_code == 200
    assert c.get("/api/users").status_code == 403
    assert c.get("/usuarios").status_code == 302


def test_cannot_delete_self_and_password_change_ends_session(secured):
    c, _ = secured
    _login(c)
    assert c.delete("/api/users/admin").status_code == 400
    c.post("/api/users", json={"username": "oper", "password": "senha-op-123"})
    op = secured[0].application.test_client()
    _login(op, "oper", "senha-op-123")
    assert op.get("/controle").status_code == 200
    c.post("/api/users/oper/password", json={"password": "nova-senha-456"})
    assert op.get("/controle").status_code == 302  # old session invalidated
    c.delete("/api/users/oper")
    assert _login(op, "oper", "nova-senha-456").headers["Location"].startswith("/login")


def test_passwords_are_hashed_and_persist(tmp_path):
    create_app(tmp_path, auth=("admin", "senha-forte-1"))
    raw = (tmp_path / "users.json").read_text()
    assert "senha-forte-1" not in raw
    c = create_app(tmp_path, auth=("admin", "senha-forte-1")).test_client()
    assert _login(c).headers["Location"] == "/controle"


def test_cross_origin_write_rejected(secured):
    c, _ = secured
    _login(c)
    r = c.post("/api/teams", data={"name": "X"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_warmup_stage(client):
    a = client.post("/api/teams", data={"name": "A"}).get_json()["teams"][0]["id"]
    b = client.post("/api/teams", data={"name": "B"}).get_json()["teams"][-1]["id"]
    assert client.post("/api/orders/0", json={"team_ids": [b, a]}).status_code == 200
    s = client.post("/api/phase", json={"phase": 0}).get_json()
    assert s["phase"] == 0 and s["phase_name"] == "Aquecimento"
    assert s["current"]["name"] == "B" and s["next"]["name"] == "A"
    assert client.post("/api/timer/start").get_json()["timer"]["running"]
    # sem pontuação: não aceita tentativas nem entra no ranking
    r = client.post("/api/attempts", json={"team_id": b, "phase": 0, "inputs": {}})
    assert r.status_code == 400
    assert all(r["total"] == 0 and r["position"] is None for r in client.get("/api/state").get_json()["ranking"])
    s = client.post("/api/timer/next").get_json()
    assert s["current"]["name"] == "A"
    assert client.post("/api/phase", json={"phase": 1}).get_json()["phase"] == 1


def test_old_state_without_warmup_loads(tmp_path):
    import json
    from frl.store import Store
    Store(tmp_path)  # cria
    st = json.loads((tmp_path / "state.json").read_text()) if (tmp_path / "state.json").exists() else None
    s = Store(tmp_path)
    s.state["orders"].pop("0")
    s._save()
    assert Store(tmp_path).state["orders"]["0"] == []
