"""Janitor: wires retention/cap/purge behind a fixed clock, run() reports the totals."""


def test_janitor_run_reports_and_records_last_run(services):
    clock = services.clock
    old = services.clips.capture_text("Viejo", source_app="a", source_title="", now=clock())
    clock.advance(days=40)
    services.janitor.run(clock.value)
    assert services.janitor.last_run == clock.value
    assert services.janitor.last_result["deleted_age"] == 1
    assert services.clips.get(old["id"]) is None


def test_janitor_uses_config_thresholds(tmp_path, clock, backend):
    from echo.config import Config
    from echo.services import Services

    config = Config(data_dir=tmp_path / "data", backend="fake", autostart=False, retention_days=1, max_clips=2, max_image_mb=200)
    svc = Services(config, clock=clock, backend=backend)
    try:
        for i in range(4):
            svc.clips.capture_text(f"clip {i}", source_app="a", source_title="", now=clock())
            clock.advance(seconds=1)
        result = svc.janitor.run(clock.value)
        assert result["deleted_cap"] == 2
        assert svc.clips.count() == 2
    finally:
        svc.stop()
