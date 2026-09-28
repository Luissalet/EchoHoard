"""Optional OCR travels through the real image store, FTS and agent API."""

from unittest.mock import patch
from subprocess import CompletedProcess

from fixtures import TINY_PNG


def test_enabled_ocr_runs_on_new_clipboard_image(tmp_path):
    from conftest import make_config
    from echo.backends.fake import FakeBackend
    from echo.services import Services

    backend = FakeBackend()
    backend.push_image(TINY_PNG, 2, 2)
    with patch("echo.ocr.read_text", return_value="Plano con cafetera Solis") as reader:
        svc = Services(make_config(tmp_path, ocr_enabled=True), backend=backend)
        try:
            clip = svc.watcher.poll_once()
            assert clip["kind"] == "image" and "cafetera Solis" in clip["text"]
            assert svc.search.search("Solis", kind="image")[0]["id"] == clip["id"]
            reader.assert_called_once_with(TINY_PNG)
        finally:
            svc.stop()


def test_image_ocr_is_searchable_and_keeps_png(client):
    svc = client.services
    calls = []
    def reader(png):
        calls.append(png)
        return "Manual de la cafetera: limpiar filtro cada semana"
    svc.clips.ocr_reader = reader
    first = svc.clips.capture_image(TINY_PNG, width=2, height=2, source_app="browser", source_title="Manual",
                                    now=svc.now())
    second = svc.clips.capture_image(TINY_PNG, width=2, height=2, source_app="browser", source_title="Manual",
                                     now=svc.now() + 1)
    assert first["id"] == second["id"] and second["times"] == 2 and len(calls) == 1
    assert svc.clips.image_path(first["id"]).read_bytes() == TINY_PNG
    assert svc.search.search("cafetera", kind="image")[0]["id"] == first["id"]
    auth = {"Authorization": f"Bearer {svc.token}"}
    search = client.post("/api/agent/call", json={"name": "clip_search", "arguments": {"q": "filtro"}}, headers=auth)
    assert search.status_code == 200 and search.json()["hits"][0]["id"] == first["id"]
    got = client.post("/api/agent/call", json={"name": "clip_get", "arguments": {"id": first["id"]}}, headers=auth)
    assert got.status_code == 200 and "[OCR local derivado]" in got.json()["text"]
    bundle = client.post("/api/agent/call", json={"name": "clip_bundle", "arguments": {"ids": [first["id"]]}}, headers=auth)
    assert bundle.status_code == 200 and "cafetera" in bundle.json()["clips"][0]["text"]


def test_ocr_failure_preserves_image_and_sensitive_text_is_not_indexed(client):
    svc = client.services
    svc.clips.ocr_reader = lambda _: (_ for _ in ()).throw(RuntimeError("OCR unavailable"))
    image = svc.clips.capture_image(TINY_PNG, width=2, height=2, source_app="a", source_title="",
                                    now=svc.now())
    assert image["text"] == "[imagen 2×2]" and svc.clips.image_path(image["id"]).exists()
    svc.clips.ocr_reader = lambda _: "sk-abcdefghijklmnopqrstuvwx"
    secret = svc.clips.capture_image(TINY_PNG + b"\x00", width=2, height=2, source_app="a", source_title="",
                                     now=svc.now())
    assert secret["sensitive"] and "abcdefghijkl" not in secret["text"]
    assert not svc.search.search("abcdefghijkl")
    auth = {"Authorization": f"Bearer {svc.token}"}
    assert client.post("/api/agent/call", json={"name": "clip_get", "arguments": {"id": secret["id"]}}, headers=auth).status_code == 403


def test_ocr_runner_missing_is_a_noop():
    from echo.ocr import read_text
    with patch("echo.ocr.shutil.which", return_value=None):
        assert read_text(TINY_PNG) == ""


def test_status_reports_ocr_configuration(client):
    assert client.get("/api/status").json()["ocr_enabled"] is False
    auth = {"Authorization": f"Bearer {client.services.token}"}
    status = client.post("/api/agent/call", json={"name": "clip_status"}, headers=auth).json()
    assert status["ocr_enabled"] is False and "ocr_available" in status


def test_ocr_runner_sends_png_to_local_tesseract():
    from echo.ocr import read_text
    with patch("echo.ocr.shutil.which", return_value="C:/tools/tesseract.exe"), \
         patch("echo.ocr.subprocess.run", return_value=CompletedProcess([], 0, b"Texto reconocido\n", b"")) as run:
        assert read_text(TINY_PNG) == "Texto reconocido"
    assert run.call_args.args[0][:3] == ["C:/tools/tesseract.exe", "stdin", "stdout"]
    assert run.call_args.kwargs["input"] == TINY_PNG
