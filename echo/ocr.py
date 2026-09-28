"""Optional local OCR for copied PNGs. No network or model service is used."""

from __future__ import annotations

import os
import shutil
import subprocess


def available() -> bool:
    return shutil.which("tesseract") is not None


def read_text(png: bytes) -> str:
    executable = shutil.which("tesseract")
    if not executable:
        return ""
    try:
        result = subprocess.run(
            [executable, "stdin", "stdout", "-l", os.environ.get("ECHO_OCR_LANG", "eng")],
            input=png, capture_output=True, timeout=12, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode:
        return ""
    return result.stdout.decode("utf-8", "replace").strip()[:20000]
