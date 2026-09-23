"""Pure detection helpers: clip kind, sensitive content, excluded apps.

No I/O, no database — every function is a plain string in, plain value out,
so the rules are directly unit-testable.
"""

from __future__ import annotations

import re

# ---------- kind detection ----------

URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
WIN_PATH_RE = re.compile(r"^[A-Za-z]:\\[^\r\n<>\"|?*]+$")
NUMBER_RE = re.compile(r"^[+-]?[$€£]?\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\s?[%€$]?$")
CODE_TEXT_MARKERS = (";", "def ", "function", "=>", "import ")

KINDS = ("text", "url", "email", "path", "code", "number", "image")


def _looks_like_path(stripped: str) -> bool:
    if WIN_PATH_RE.match(stripped):
        return True
    if stripped.startswith("/") and len(stripped) > 1 and not re.search(r"\s", stripped):
        return True
    return False


def _has_indented_line(lines: list[str]) -> bool:
    # The first line never counts: a wrapped sentence often starts flush left
    # and a quoted snippet's first line rarely carries the indentation cue.
    return any(line[:1] in (" ", "\t") and line.strip() for line in lines[1:])


def detect_kind(text: str) -> str:
    """One of KINDS, from the clipboard text alone (never called for images)."""
    stripped = (text or "").strip()
    if not stripped:
        return "text"
    if "\n" not in stripped:
        if URL_RE.match(stripped):
            return "url"
        if EMAIL_RE.match(stripped):
            return "email"
        if _looks_like_path(stripped):
            return "path"
        if NUMBER_RE.match(stripped):
            return "number"
        return "text"
    # Multi-line: code needs 2+ distinct markers (braces, semicolons, def/function/=>/import, indentation).
    lines = stripped.splitlines()
    markers = [
        "{" in stripped or "}" in stripped,
        any(m in stripped for m in CODE_TEXT_MARKERS),
        _has_indented_line(lines),
    ]
    if sum(markers) >= 2:
        return "code"
    return "text"


# ---------- sensitive-content detection ----------

PASSWORD_WINDOW_HINTS = ("password", "contraseña", "1password", "bitwarden", "keepass", "vault", "login")
TOKEN_PREFIXES = ("sk-", "ghp_", "xox", "AKIA")
JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
URL_OR_EMAIL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://|^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _char_classes(s: str) -> int:
    classes = 0
    if re.search(r"[a-z]", s):
        classes += 1
    if re.search(r"[A-Z]", s):
        classes += 1
    if re.search(r"\d", s):
        classes += 1
    if re.search(r"[^A-Za-z0-9]", s):
        classes += 1
    return classes


def _looks_like_password_token(s: str) -> bool:
    if " " in s or "\n" in s or len(s) < 8:
        return False
    if URL_OR_EMAIL_RE.match(s):
        return False
    return _char_classes(s) >= 2


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(digits[::-1]):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total > 0 and total % 10 == 0


def iban_ok(s: str) -> bool:
    s = s.replace(" ", "").upper()
    if not IBAN_RE.match(s):
        return False
    rearranged = s[4:] + s[:4]
    try:
        numeric = "".join(str(int(c, 36)) for c in rearranged)
        return int(numeric) % 97 == 1
    except ValueError:
        return False


def detect_sensitive(text: str, window_title: str = "") -> str | None:
    """Return a Spanish label ("contraseña"|"token"|"tarjeta"|"iban") when the
    content looks sensitive, else None. Called with the RAW text; the caller
    is responsible for never persisting or logging it when this returns non-None.
    """
    stripped = (text or "").strip()
    if not stripped:
        return None
    title_l = (window_title or "").lower()

    if any(stripped.startswith(p) for p in TOKEN_PREFIXES) and " " not in stripped and "\n" not in stripped:
        return "token"
    if stripped.startswith("Bearer ") and "\n" not in stripped:
        return "token"
    if "\n" not in stripped and stripped.count(".") == 2 and JWT_RE.match(stripped):
        return "token"

    # Structural formats (IBAN, card) are checked before the generic password
    # heuristic: a 22-char IBAN is exactly the shape "8+ chars, 2+ classes,
    # no spaces" too, but it is an IBAN, not a password.
    if iban_ok(stripped):
        return "iban"

    digits_only = re.sub(r"[ -]", "", stripped)
    if re.fullmatch(r"\d{13,19}", digits_only) and luhn_ok(digits_only):
        return "tarjeta"

    if _looks_like_password_token(stripped):
        if len(stripped) >= 16:
            return "contraseña"
        if any(hint in title_l for hint in PASSWORD_WINDOW_HINTS):
            return "contraseña"

    return None


# ---------- app exclusion ----------


def normalise_app(name: str) -> str:
    name = (name or "").strip().lower()
    return name[:-4] if name.endswith(".exe") else name


def is_excluded_app(app: str, excluded: tuple[str, ...]) -> bool:
    normalized = normalise_app(app)
    if not normalized:
        return False
    return normalized in {normalise_app(e) for e in excluded}
