"""HTTP API through TestClient: health/status/pause, clips CRUD, search, agent auth."""

import datetime as dt

from fixtures import TINY_PNG


def test_health_and_local_only(client):
    body = client.get("/api/health").json()
    assert body["service"] == "echo-hoard" and body["dataDirConfigured"] is True
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
    assert client.get("/api/status", headers={"origin": "http://evil.example"}).status_code == 403
    assert client.get("/api/nope").status_code == 404


def test_status_reports_backend_and_counts(client):
    status = client.get("/api/status").json()
    assert status["backend"] == "fake"
    assert status["clips_count"] == 0
    assert status["paused"] is False


def test_pause_and_resume(client):
    paused = client.post("/api/pause").json()
    assert paused["paused"] is True
    status = client.get("/api/status").json()
    assert status["paused"] is True
    resumed = client.post("/api/resume").json()
    assert resumed["paused"] is False


def test_add_clip_sets_clipboard_and_stores_it(client):
    result = client.post("/api/clips", json={"text": "Cópiame esto"}).json()
    assert result["text"] == "Cópiame esto"
    assert result["source_app"] == "assistant"
    assert client.backend.written[-1] == "Cópiame esto"


def test_add_clip_rejects_empty_text(client):
    assert client.post("/api/clips", json={"text": ""}).status_code == 400


def test_list_clips_and_filters(client):
    client.post("/api/clips", json={"text": "https://valdeniebla.example"})
    client.post("/api/clips", json={"text": "una frase normal"})
    listing = client.get("/api/clips").json()
    assert listing["count"] == 2
    urls = client.get("/api/clips", params={"kind": "url"}).json()
    assert urls["count"] == 1 and urls["clips"][0]["kind"] == "url"


def test_get_patch_and_delete_clip(client):
    created = client.post("/api/clips", json={"text": "Editable"}).json()
    clip_id = created["id"]
    fetched = client.get(f"/api/clips/{clip_id}").json()
    assert fetched["text"] == "Editable"

    patched = client.patch(f"/api/clips/{clip_id}", json={"label": "Importante", "tags": ["a", "b"], "pinned": True}).json()
    assert patched["label"] == "Importante"
    assert patched["pinned"] is True

    assert client.delete(f"/api/clips/{clip_id}").json() == {"ok": True}
    assert client.get(f"/api/clips/{clip_id}").status_code == 404
    assert client.delete(f"/api/clips/{clip_id}").status_code == 404

    restored = client.post(f"/api/clips/{clip_id}/restore").json()
    assert restored == {"ok": True}
    assert client.get(f"/api/clips/{clip_id}").status_code == 200


def test_copy_clip_writes_the_clipboard(client):
    created = client.post("/api/clips", json={"text": "Vuelve a copiarme"}).json()
    copied = client.post(f"/api/clips/{created['id']}/copy").json()
    assert copied["id"] == created["id"]
    assert client.backend.written[-1] == "Vuelve a copiarme"


def test_copy_refuses_sensitive_clip(client):
    services = client.services
    clip = services.clips.capture_text("sk-abcdefghijklmnopqrstuvwx", source_app="terminal", source_title="", now=services.now())
    response = client.post(f"/api/clips/{clip['id']}/copy")
    assert response.status_code == 403


def test_image_bytes_are_served(client):
    services = client.services
    clip = services.clips.capture_image(TINY_PNG, width=2, height=2, source_app="a", source_title="", now=services.now())
    response = client.get(f"/api/clips/{clip['id']}/image")
    assert response.status_code == 200
    assert response.content == TINY_PNG
    assert response.headers["content-type"] == "image/png"


def test_bulk_purge_before(client):
    clock = client.clock
    old = client.post("/api/clips", json={"text": "Antiguo"}).json()
    clock.advance(days=1)
    cutoff = clock.value
    clock.advance(days=1)
    result = client.delete("/api/clips", params={"before": dt.datetime.fromtimestamp(cutoff, dt.timezone.utc).isoformat()})
    assert result.status_code == 200
    assert result.json()["deleted"] == 1
    assert client.get(f"/api/clips/{old['id']}").status_code == 404


def test_search_endpoint(client):
    client.post("/api/clips", json={"text": "Informe de Valdeniebla"})
    result = client.get("/api/search", params={"q": "valdeniebla"}).json()
    assert result["count"] >= 1
    assert "<mark>" in result["hits"][0]["snippet"]


def test_agent_tools_and_auth(client):
    catalog = client.get("/api/agent/tools").json()
    names = [t["name"] for t in catalog["tools"]]
    assert names == ["clip_recent", "clip_search", "clip_get", "clip_set", "clip_copy", "clip_pin",
                      "clip_delete", "clip_status", "clip_capture"]
    for tool in catalog["tools"]:
        assert "Sinónimos:" in tool["description"] and tool["inputSchema"]["type"] == "object"
    write = next(t for t in catalog["tools"] if t["name"] == "clip_set")
    assert write["annotations"]["readOnlyHint"] is False
    destructive = next(t for t in catalog["tools"] if t["name"] == "clip_delete")
    assert destructive["annotations"]["destructiveHint"] is True

    token = client.services.token
    assert client.post("/api/agent/call", json={"name": "clip_status"}).status_code == 401
    assert client.post("/api/agent/call", json={"name": "clip_status"}, headers={"Authorization": "Bearer nope"}).status_code == 401
    auth = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/agent/call", json={"name": "unknown"}, headers=auth).status_code == 404

    status = client.post("/api/agent/call", json={"name": "clip_status"}, headers=auth).json()
    assert status["watching"] is False  # autostart is off in tests

    set_result = client.post("/api/agent/call", json={"name": "clip_set", "arguments": {"text": "Del asistente"}}, headers=auth).json()
    assert set_result["ok"] is True
    clip_id = set_result["clip"]["id"]
    assert client.backend.written[-1] == "Del asistente"

    recent = client.post("/api/agent/call", json={"name": "clip_recent", "arguments": {"n": 5}}, headers=auth).json()
    assert recent["count"] >= 1

    got = client.post("/api/agent/call", json={"name": "clip_get", "arguments": {"id": clip_id}}, headers=auth).json()
    assert got["text"] == "Del asistente"

    pinned = client.post("/api/agent/call", json={"name": "clip_pin", "arguments": {"id": clip_id, "pinned": True, "label": "top"}}, headers=auth).json()
    assert pinned["pinned"] is True and pinned["label"] == "top"

    copied = client.post("/api/agent/call", json={"name": "clip_copy", "arguments": {"id": clip_id}}, headers=auth).json()
    assert copied["ok"] is True

    paused = client.post("/api/agent/call", json={"name": "clip_capture", "arguments": {"action": "pause"}}, headers=auth).json()
    assert paused["paused"] is True
    resumed = client.post("/api/agent/call", json={"name": "clip_capture", "arguments": {"action": "resume"}}, headers=auth).json()
    assert resumed["paused"] is False

    deleted = client.post("/api/agent/call", json={"name": "clip_delete", "arguments": {"id": clip_id}}, headers=auth).json()
    assert deleted["ok"] is True
    assert client.post("/api/agent/call", json={"name": "clip_get", "arguments": {"id": clip_id}}, headers=auth).status_code == 404


def test_agent_clip_get_refuses_sensitive_content(client):
    services = client.services
    clip = services.clips.capture_text("sk-abcdefghijklmnopqrstuvwx", source_app="terminal", source_title="", now=services.now())
    token = client.services.token
    auth = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/agent/call", json={"name": "clip_get", "arguments": {"id": clip["id"]}}, headers=auth)
    assert response.status_code == 403
    recent = client.post("/api/agent/call", json={"name": "clip_recent", "arguments": {"n": 5}}, headers=auth).json()
    hit = next(c for c in recent["clips"] if c["id"] == clip["id"])
    assert hit["preview"] == "[oculto]"


def test_agent_clip_copy_refuses_sensitive_without_allow_flag(client):
    services = client.services
    clip = services.clips.capture_text("AKIAABCDEFGHIJKLMNOP", source_app="terminal", source_title="", now=services.now())
    token = client.services.token
    auth = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/agent/call", json={"name": "clip_copy", "arguments": {"id": clip["id"]}}, headers=auth)
    assert response.status_code == 403
    allowed = client.post("/api/agent/call", json={"name": "clip_copy", "arguments": {"id": clip["id"], "allow_sensitive": True}}, headers=auth)
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


def test_agent_since_accepts_human_windows(client):
    client.post("/api/clips", json={"text": "Copiado hace un momento"})
    auth = {"Authorization": f"Bearer {client.services.token}"}
    call = lambda name, args: client.post("/api/agent/call", json={"name": name, "arguments": args}, headers=auth)  # noqa: E731
    fresh = call("clip_recent", {"n": 10, "since": "1h"}).json()
    assert fresh["count"] >= 1 and "since" in fresh
    assert call("clip_recent", {"n": 10, "since": "2999-01-01"}).json()["count"] == 0
    assert call("clip_search", {"q": "momento", "since": "hoy"}).json()["count"] >= 1
    bad = call("clip_recent", {"since": "cuando sea"})
    assert bad.status_code == 400 and "since accepts" in bad.text
