"""The watcher driven synchronously (poll_once) and as a real thread against the fake backend."""

import time

from echo.watcher import Watcher
from fixtures import TINY_PNG


def test_poll_once_returns_none_when_nothing_new(services, backend):
    assert services.watcher.poll_once() is None


def test_poll_once_captures_text_and_advances_the_clock(services, backend, clock):
    backend.push_text("Primera copia", app="notas", title="Notas sin título")
    clip = services.watcher.poll_once()
    assert clip is not None
    assert clip["text"] == "Primera copia"
    assert clip["source_app"] == "notas"
    assert services.watcher.last_capture_at == clock.value


def test_poll_once_skips_excluded_apps(tmp_path, clock):
    from echo.backends.fake import FakeBackend
    from echo.config import Config
    from echo.services import Services

    backend = FakeBackend()
    config = Config(data_dir=tmp_path / "data", backend="fake", autostart=False, exclude_apps=("bitwarden",))
    svc = Services(config, clock=clock, backend=backend)
    try:
        backend.push_text("contraseña-super-secreta", app="Bitwarden.exe", title="Bitwarden")
        clip = svc.watcher.poll_once()
        assert clip is None
        assert svc.clips.count() == 0
        assert svc.watcher.skipped_excluded == 1
    finally:
        svc.stop()


def test_poll_once_ignores_blank_text(services, backend):
    backend.push_text("   \n  ")
    assert services.watcher.poll_once() is None
    assert services.clips.count() == 0


def test_poll_once_captures_images(services, backend):
    backend.push_image(TINY_PNG, 2, 2)
    clip = services.watcher.poll_once()
    assert clip is not None and clip["kind"] == "image"
    assert services.clips.image_path(clip["id"]) is not None


def test_dedupe_across_two_polls_bumps_times(services, backend, clock):
    backend.push_text("Repetido", app="a", title="")
    first = services.watcher.poll_once()
    clock.advance(seconds=10)
    backend.push_text("Repetido", app="b", title="")
    second = services.watcher.poll_once()
    assert second["id"] == first["id"]
    assert second["times"] == 2


def test_watcher_thread_drives_three_pushes_to_three_clips(services, backend):
    """No test asserts on wall-clock values here — only that, after the fake
    backend's queue drains, the store ended up with the right clips. The
    fixed FakeClock still stamps every row, so timestamps stay deterministic."""
    backend.push_text("Uno", app="a", title="")
    backend.push_text("Dos", app="a", title="")
    backend.push_text("Uno", app="a", title="")  # dedupes with the first

    services.watcher.start()
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and services.watcher.captured < 3:
            time.sleep(0.01)
    finally:
        services.watcher.stop()

    assert services.clips.count() == 2
    one = next(c for c in services.clips.list(limit=10) if c["preview"] == "Uno")
    assert one["times"] == 2
    assert services.watcher.running() is False


def test_watcher_pause_resume_stops_and_restarts_polling(services, backend):
    services.watcher.start()
    try:
        services.watcher.pause()
        backend.push_text("Mientras pausado", app="a", title="")
        time.sleep(0.1)
        assert services.clips.count() == 0

        services.watcher.resume()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and services.clips.count() < 1:
            time.sleep(0.01)
        assert services.clips.count() == 1
    finally:
        services.watcher.stop()


def test_watcher_start_stop_is_idempotent_and_clean(backend, clock):
    from echo.store import ClipStore
    from echo.db import Database

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        db = Database(Path(td) / "t.db")
        store = ClipStore(db, Path(td) / "images")
        watcher = Watcher(backend, store, clock=clock)
        watcher.start()
        watcher.start()  # no-op, does not spawn a second thread
        assert watcher.running() is True
        watcher.stop()
        watcher.stop()  # no-op
        assert watcher.running() is False
        db.close()
