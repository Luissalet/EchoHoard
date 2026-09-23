"""Kind detection and sensitive-content detection: pure functions, table-driven."""

import pytest

from echo.detect import detect_kind, detect_sensitive, is_excluded_app, luhn_ok


# ---------- kind detection ----------

@pytest.mark.parametrize("text,expected", [
    ("", "text"),
    ("   ", "text"),
    ("Hola, esto es una frase normal.", "text"),
    ("https://valdeniebla.example/ruta?x=1", "url"),
    ("http://valdeniebla.example", "url"),
    ("no es una url: https://valdeniebla.example", "text"),  # not the *whole* clip
    ("contacto@valdeniebla.example", "email"),
    (r"C:\Users\ana\Documentos\informe.pdf", "path"),
    ("/home/ana/informe.pdf", "path"),
    ("42", "number"),
    ("-3.5", "number"),
    ("1.234,56", "number"),
    ("$12.50", "number"),
    ("12,50 €", "number"),
])
def test_detect_kind_single_line(text, expected):
    assert detect_kind(text) == expected


def test_detect_kind_code_needs_two_markers_and_multiple_lines():
    code = "def saluda(nombre):\n    return f\"Hola, {nombre}\"\n"
    assert detect_kind(code) == "code"


def test_detect_kind_multiline_plain_text_is_not_code():
    poem = "Primera línea del poema\nsegunda línea sin nada especial\ntercera línea tampoco"
    assert detect_kind(poem) == "text"


def test_detect_kind_one_marker_is_not_enough():
    almost = "una frase;\notra frase sin más marcadores"
    assert detect_kind(almost) == "text"


def test_detect_kind_javascript_style_code():
    js = "const saluda = (nombre) => {\n  return `Hola, ${nombre}`;\n};"
    assert detect_kind(js) == "code"


# ---------- sensitive detection ----------

def test_password_flagged_by_window_title_hint():
    assert detect_sensitive("Tr0ub4dor&3", "Bitwarden — inicio de sesión") == "contraseña"
    assert detect_sensitive("Tr0ub4dor&3", "Editor de texto") is None  # same token, no hint, short enough


def test_password_flagged_regardless_of_window_when_long_enough():
    assert detect_sensitive("Xk9#mQ2vBp7$wLz4nR", "Bloc de notas") == "contraseña"


def test_negative_normal_sentence_is_not_sensitive():
    assert detect_sensitive("Nos vemos el jueves a las diez en el despacho.", "") is None


def test_negative_plain_16_char_word_is_not_sensitive():
    assert detect_sensitive("abcdefghijklmnop", "Bitwarden") is None  # one character class only


def test_negative_url_is_not_sensitive():
    assert detect_sensitive("https://valdeniebla.example/documentos/informe-2024", "Bitwarden") is None


def test_api_key_prefixes_are_tokens():
    assert detect_sensitive("sk-abcdefghijklmnopqrstuvwx", "") == "token"
    assert detect_sensitive("ghp_abcdefghijklmnopqrstuvwxyz0123456789", "") == "token"
    assert detect_sensitive("Bearer abcdefghijklmnop", "") == "token"


def test_jwt_like_string_is_a_token():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    assert detect_sensitive(jwt, "") == "token"


def test_luhn_ok_validates_a_well_known_test_number():
    assert luhn_ok("4111111111111111") is True
    assert luhn_ok("4111111111111112") is False


def test_credit_card_number_is_flagged():
    assert detect_sensitive("4111 1111 1111 1111", "") == "tarjeta"
    assert detect_sensitive("4111111111111112", "") is None  # fails Luhn


def test_negative_bare_number_is_not_a_card():
    assert detect_sensitive("42", "") is None


def test_iban_is_flagged():
    # GB29 NWBK 6016 1331 9268 19 is the well-known IBAN checksum example.
    assert detect_sensitive("GB29NWBK60161331926819", "") == "iban"
    assert detect_sensitive("GB29NWBK123", "") is None  # too short to be an IBAN, too short to be a bare password


# ---------- excluded apps ----------

def test_excluded_apps_match_case_insensitively_and_ignore_exe():
    excluded = ("KeePass", "1Password", "Bitwarden", "keepassxc")
    assert is_excluded_app("Bitwarden.exe", excluded) is True
    assert is_excluded_app("keepassxc", excluded) is True
    assert is_excluded_app("KEEPASS", excluded) is True
    assert is_excluded_app("notepad", excluded) is False
    assert is_excluded_app("", excluded) is False


def test_bmp_file_header_offsets():
    """The clipboard DIB's pixel offset depends on its header, palette and masks."""
    from echo.backends.windows import _bmp_file_header

    def offset(dib):
        return int.from_bytes(_bmp_file_header(dib)[10:14], "little")

    plain24 = (40).to_bytes(4, "little") + b"\x00" * 10 + (24).to_bytes(2, "little") + (0).to_bytes(4, "little") + b"\x00" * 20
    assert offset(plain24) == 54
    fields32 = (40).to_bytes(4, "little") + b"\x00" * 10 + (32).to_bytes(2, "little") + (3).to_bytes(4, "little") + b"\x00" * 20
    assert offset(fields32) == 54 + 12
    pal8 = (40).to_bytes(4, "little") + b"\x00" * 10 + (8).to_bytes(2, "little") + (0).to_bytes(4, "little") + b"\x00" * 12 + (16).to_bytes(4, "little") + b"\x00" * 4
    assert offset(pal8) == 54 + 16 * 4
    v5 = (124).to_bytes(4, "little") + b"\x00" * 10 + (32).to_bytes(2, "little") + (3).to_bytes(4, "little") + b"\x00" * 104
    assert offset(v5) == 14 + 124
