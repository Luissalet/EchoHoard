"""Obviously fictional clipboard content for the tests."""

from __future__ import annotations

SAMPLE_TEXTS = [
    "Reunión de Valdeniebla el jueves a las 10",
    "https://valdeniebla.example/informe",
    "contacto@valdeniebla.example",
    "42",
]

SAMPLE_CODE = """def saluda(nombre):
    return f"Hola, {nombre}"
"""

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
    "0000001649444154789c63acd0886260606062606060606000000c0000feb0d8e50f"
    "0000000049454e44ae426082"
)
TINY_PNG_SIZE = (2, 2)
