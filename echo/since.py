"""Human time windows for the assistant: «1h», «hace 2 horas», «hoy», «ayer», an ISO date or epoch seconds.

A local model is poor at computing Unix timestamps, so every ``since`` a tool accepts goes through
:func:`resolve_since`, which answers epoch seconds or raises ``ValueError`` with the accepted forms.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Optional, Union

SINCE_HELP = ("since accepts epoch seconds, an ISO date/time (2026-09-25, 2026-09-25T10:30), an age "
              "(30m, 2h, 3d, 1w, «hace 2 horas», «2 hours ago»), or a word: hoy/today, ayer/yesterday, "
              "esta mañana/this morning, esta semana/this week, este mes/this month, "
              "última hora/last hour.")

_UNITS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1, "seg": 1, "segundo": 1, "segundos": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60, "minuto": 60, "minutos": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600, "hora": 3600, "horas": 3600,
    "d": 86400, "day": 86400, "days": 86400, "dia": 86400, "dias": 86400, "día": 86400, "días": 86400,
    "w": 604800, "week": 604800, "weeks": 604800, "semana": 604800, "semanas": 604800,
}
_AGE = re.compile(r"^(?:hace\s+)?(\d+(?:[.,]\d+)?)\s*([a-záéíóú]+)(?:\s+ago)?$")
_ONE = re.compile(r"^(?:la\s+|el\s+|the\s+)?(?:última|ultima|último|ultimo|last|past)\s+([a-záéíóú]+)$")


def _midnight(now: float) -> datetime:
    return datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)


def resolve_since(value: Union[str, float, int, None], now: Optional[float] = None) -> Optional[float]:
    """Epoch seconds for ``value`` (None stays None). Raises ValueError(SINCE_HELP) when unreadable."""
    if value is None:
        return None
    now = time.time() if now is None else now
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if re.fullmatch(r"\d{9,}(\.\d+)?", text):
        return float(text)
    words = {
        "hoy": 0, "today": 0, "ayer": 1, "yesterday": 1,
    }
    if text in words:
        return (_midnight(now) - timedelta(days=words[text])).timestamp()
    if text in ("esta mañana", "esta manana", "this morning"):
        return _midnight(now).replace(hour=6).timestamp()
    if text in ("esta semana", "this week"):
        day = _midnight(now)
        return (day - timedelta(days=day.weekday())).timestamp()
    if text in ("este mes", "this month"):
        return _midnight(now).replace(day=1).timestamp()
    one = _ONE.match(text)
    if one and one.group(1) in _UNITS:
        return now - _UNITS[one.group(1)]
    age = _AGE.match(text)
    if age and age.group(2) in _UNITS:
        return now - float(age.group(1).replace(",", ".")) * _UNITS[age.group(2)]
    try:
        return datetime.fromisoformat(text.replace("z", "+00:00")).timestamp()
    except ValueError:
        pass
    raise ValueError(SINCE_HELP)


__all__ = ["resolve_since", "SINCE_HELP"]
