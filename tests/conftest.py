import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for entry in (str(ROOT), str(ROOT / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

warnings.filterwarnings("ignore", category=DeprecationWarning)

from echo.backends.fake import FakeBackend  # noqa: E402
from echo.config import Config  # noqa: E402
from echo.main import create_app  # noqa: E402
from echo.services import Services  # noqa: E402


class FakeClock:
    """A settable clock: `now()` returns `.value`; `.advance(seconds)` moves it.
    Every service and store call takes `now` explicitly, so pinning this fixture
    makes retention, dedupe timestamps and janitor sweeps fully deterministic.
    """

    def __init__(self, start: float = 1_700_000_000.0):  # 2023-11-14 22:13:20 UTC
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float = 0, days: float = 0) -> None:
        self.value += seconds + days * 86400


def make_config(tmp_path: Path, **overrides) -> Config:
    base = dict(data_dir=tmp_path / "data", data_dir_configured=True, backend="fake", autostart=False)
    base.update(overrides)
    return Config(**base)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def services(tmp_path, clock, backend):
    svc = Services(make_config(tmp_path), clock=clock, backend=backend)
    yield svc
    svc.stop()


@pytest.fixture
def client(tmp_path, clock, backend):
    from fastapi.testclient import TestClient

    svc = Services(make_config(tmp_path), clock=clock, backend=backend)
    app = create_app(make_config(tmp_path), services=svc)
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        test_client.services = app.state.services
        test_client.clock = clock
        test_client.backend = backend
        yield test_client
