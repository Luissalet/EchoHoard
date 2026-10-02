"""OCR for copied PNGs.

The family has one OCR engine, Kafka's Hoard, reached through the hub (`fam_docs.ocr_image`); it reads Spanish by
default. Without it (hub or Kafka down, no engine installed there) a local Tesseract is used, found by
`hoard_link.proc.find_exe` (PATH, `ECHO_TESSERACT`, the standard Windows install folders) and run without a console
window. Nothing leaves the machine either way.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

from .hoard_link import fam_docs, proc

log = logging.getLogger("echo.ocr")

MAX_CHARS = 20000
LOCAL_TIMEOUT_S = 12
# Tesseract's three-letter packs to the ISO codes the family service takes.
ISO = {"spa": "es", "eng": "en", "fra": "fr", "deu": "de", "ita": "it", "por": "pt", "cat": "ca"}
DEFAULT_TESSERACT_LANG = "spa+eng"
WINDOWS_DIRS = (r"C:\Program Files\Tesseract-OCR", r"C:\Program Files (x86)\Tesseract-OCR")


def configured_lang() -> str:
    """ECHO_OCR_LANG as Tesseract spells it (`eng`, `spa+eng`); Spanish and English by default."""
    return (os.environ.get("ECHO_OCR_LANG") or "").strip() or DEFAULT_TESSERACT_LANG


def service_lang(tesseract_lang: str | None = None) -> str:
    """The ISO code for the family service: the first language of ECHO_OCR_LANG (`spa+eng` -> `es`)."""
    first = (tesseract_lang or configured_lang()).split("+")[0].strip().lower()
    return ISO.get(first, first if len(first) == 2 else "es")


_FOUND: dict = {"at": 0.0, "key": None, "path": None}


def tesseract() -> str | None:
    """The Tesseract executable, or None. Looking runs the candidate (`--version`), so the answer is kept for 30 s
    (the status page polls `available()`)."""
    key = (os.environ.get("ECHO_TESSERACT"), os.environ.get("HOARD_TESSERACT"), os.environ.get("PATH"))
    if _FOUND["key"] == key and time.monotonic() - _FOUND["at"] < 30.0:
        return _FOUND["path"]
    path = proc.find_exe("tesseract", explicit=os.environ.get("ECHO_TESSERACT"), env_vars=("HOARD_TESSERACT",),
                         extra_dirs=WINDOWS_DIRS, verify_args=["--version"])
    _FOUND.update(at=time.monotonic(), key=key, path=path)
    return path


def available() -> bool:
    """Text can be read from images: a local Tesseract or Kafka's engine through the hub."""
    return tesseract() is not None or fam_docs.available()


def _local(png: bytes) -> str:
    exe = tesseract()
    if not exe:
        return ""
    langs = [configured_lang()]
    if langs[0] != "eng":
        langs.append("eng")  # a missing language pack makes Tesseract fail outright: retry with the one that always ships
    for lang in langs:
        try:
            result = proc.run([exe, "stdin", "stdout", "-l", lang], input=png, text=False, timeout=LOCAL_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if not result.returncode:
            return (result.stdout or b"").decode("utf-8", "replace").strip()[:MAX_CHARS]
    return ""


def read_text(png: bytes, *, work_dir: Path | None = None) -> str:
    """The text in a PNG. Kafka's engine first (the screenshot is written to `work_dir` for it, since the service takes
    paths, and removed afterwards), the local Tesseract when it cannot be used. Empty string when nothing reads it."""
    target = Path(work_dir) if work_dir else Path(tempfile.gettempdir()) / "echo-hoard-ocr"
    path: Path | None = None
    try:
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{hashlib.sha256(png).hexdigest()[:24]}.png"
        path.write_bytes(png)
        got = fam_docs.ocr_image(str(path), lang=service_lang())
        if got.get("ok"):
            return str(got.get("text") or "").strip()[:MAX_CHARS]
        if got.get("kind") == "auth":
            log.warning("OCR through the family service refused the app's token; using the local engine")
    except Exception as error:  # noqa: BLE001 - OCR is optional, the clip is stored either way
        log.debug("family OCR failed: %s", error)
    finally:
        if path is not None:
            try:
                path.unlink()
            except OSError:
                pass
    return _local(png)
