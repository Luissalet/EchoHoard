from datetime import datetime

import pytest

from echo.since import SINCE_HELP, resolve_since

NOW = datetime(2026, 9, 25, 14, 30).timestamp()  # a Friday


@pytest.mark.parametrize("text,seconds", [
    ("1h", 3600), ("30m", 1800), ("2 horas", 7200), ("hace 2 horas", 7200), ("2 hours ago", 7200),
    ("3d", 3 * 86400), ("1w", 604800), ("última hora", 3600), ("the last hour", 3600), ("1,5h", 5400),
])
def test_ages(text, seconds):
    assert resolve_since(text, NOW) == pytest.approx(NOW - seconds)


def test_words():
    assert datetime.fromtimestamp(resolve_since("hoy", NOW)) == datetime(2026, 9, 25)
    assert datetime.fromtimestamp(resolve_since("ayer", NOW)) == datetime(2026, 9, 24)
    assert datetime.fromtimestamp(resolve_since("esta mañana", NOW)) == datetime(2026, 9, 25, 6)
    assert datetime.fromtimestamp(resolve_since("esta semana", NOW)) == datetime(2026, 9, 21)
    assert datetime.fromtimestamp(resolve_since("este mes", NOW)) == datetime(2026, 9, 1)


def test_epoch_iso_and_none():
    assert resolve_since(1788000000, NOW) == 1788000000.0
    assert resolve_since("1788000000", NOW) == 1788000000.0
    assert datetime.fromtimestamp(resolve_since("2026-09-20T10:30", NOW)) == datetime(2026, 9, 20, 10, 30)
    assert resolve_since(None, NOW) is None and resolve_since("", NOW) is None


def test_unreadable_says_what_is_accepted():
    with pytest.raises(ValueError) as err:
        resolve_since("cuando sea", NOW)
    assert str(err.value) == SINCE_HELP
