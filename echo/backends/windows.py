"""Windows clipboard backend: ctypes against user32/kernel32 only, no pywin32.

Import-safe on any platform — every ctypes call lives inside `__init__` or a
method, guarded by `IS_WINDOWS`, so importing this module on Linux/macOS never
touches a missing DLL. `read()` polls `GetClipboardSequenceNumber` (cheap) and
only opens the clipboard when it changed. If another process holds the
clipboard lock, `OpenClipboard` is retried a few times and the change is
skipped rather than crashing the app.
"""

from __future__ import annotations

import ctypes
import io
import logging
import sys
import time
from ctypes import wintypes

from .base import ClipboardBackend, ClipboardContent

log = logging.getLogger("echo.backend.windows")

IS_WINDOWS = sys.platform == "win32"

CF_UNICODETEXT = 13
CF_DIB = 8
CF_DIBV5 = 17
GMEM_MOVEABLE = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _bmp_file_header(dib: bytes) -> bytes:
    """The 14-byte BITMAPFILEHEADER that turns a clipboard DIB into a .bmp."""
    header_size = int.from_bytes(dib[0:4], "little") if len(dib) >= 4 else 40
    bits = int.from_bytes(dib[14:16], "little") if len(dib) >= 16 else 24
    compression = int.from_bytes(dib[16:20], "little") if len(dib) >= 20 else 0
    colours_used = int.from_bytes(dib[32:36], "little") if len(dib) >= 36 else 0
    palette = 0
    if bits <= 8:
        palette = (colours_used or (1 << bits)) * 4
    masks = 12 if (compression == 3 and header_size == 40) else 0  # BI_BITFIELDS after a V3 header
    offset = 14 + header_size + palette + masks
    return b"BM" + (len(dib) + 14).to_bytes(4, "little") + b"\x00\x00\x00\x00" + offset.to_bytes(4, "little")


class WindowsBackend(ClipboardBackend):
    name = "windows"
    poll_interval = 0.3

    def __init__(self):
        if not IS_WINDOWS:
            raise RuntimeError("The Windows clipboard backend only works on Windows.")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_signatures()
        self._last_seq: int | None = None
        self._proc_names: dict[int, str] = {}

    def _configure_signatures(self) -> None:
        u, k = self._user32, self._kernel32
        u.GetClipboardSequenceNumber.restype = wintypes.DWORD
        u.OpenClipboard.restype = wintypes.BOOL
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.CloseClipboard.restype = wintypes.BOOL
        u.GetClipboardData.restype = wintypes.HANDLE
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.SetClipboardData.restype = wintypes.HANDLE
        u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u.EmptyClipboard.restype = wintypes.BOOL
        u.IsClipboardFormatAvailable.restype = wintypes.BOOL
        u.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        k.GlobalLock.restype = wintypes.LPVOID
        k.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k.GlobalUnlock.restype = wintypes.BOOL
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k.GlobalAlloc.restype = wintypes.HGLOBAL
        k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k.GlobalSize.restype = ctypes.c_size_t
        k.GlobalSize.argtypes = [wintypes.HGLOBAL]
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.CloseHandle.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]

    def _open(self, retries: int = 5, delay: float = 0.05) -> bool:
        """A few short retries: another app (a password manager clearing its own
        clip, a screen reader) can hold the clipboard lock for a moment."""
        for _ in range(retries):
            if self._user32.OpenClipboard(None):
                return True
            time.sleep(delay)
        return False

    # ---------- read ----------
    def read(self) -> ClipboardContent | None:
        seq = self._user32.GetClipboardSequenceNumber()
        if seq == self._last_seq:
            return None
        self._last_seq = seq
        if not self._open():
            log.debug("clipboard busy; skipping this change")
            return None
        try:
            if self._user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return self._read_text()
            if self._user32.IsClipboardFormatAvailable(CF_DIB) or self._user32.IsClipboardFormatAvailable(CF_DIBV5):
                return self._read_image()
            return None
        finally:
            self._user32.CloseClipboard()

    def _read_text(self) -> ClipboardContent | None:
        handle = self._user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        locked = self._kernel32.GlobalLock(handle)
        if not locked:
            return None
        try:
            text = ctypes.wstring_at(locked)
        finally:
            self._kernel32.GlobalUnlock(handle)
        return ClipboardContent(kind="text", text=text)

    def _read_image(self) -> ClipboardContent | None:
        from PIL import Image  # local import: Pillow is only needed on this path

        # CF_DIB first: Windows synthesises it from CF_DIBV5 and its 40-byte
        # header is the one every decoder knows.
        fmt = CF_DIB if self._user32.IsClipboardFormatAvailable(CF_DIB) else CF_DIBV5
        handle = self._user32.GetClipboardData(fmt)
        if not handle:
            return None
        size = self._kernel32.GlobalSize(handle)
        locked = self._kernel32.GlobalLock(handle)
        if not locked:
            return None
        try:
            raw = ctypes.string_at(locked, size)
        finally:
            self._kernel32.GlobalUnlock(handle)
        try:
            # A DIB has no BMP file header; prefix one so Pillow can decode it.
            # The pixel offset depends on the DIB header size, the palette and
            # the BI_BITFIELDS masks — 54 is only right for a plain 24-bit DIB.
            image = Image.open(io.BytesIO(_bmp_file_header(raw) + raw))
            image.load()
        except Exception as error:
            log.debug("could not decode the clipboard image: %s", error)
            return None
        buf = io.BytesIO()
        image.convert("RGB").save(buf, "PNG")
        return ClipboardContent(kind="image", image_png=buf.getvalue(), width=image.width, height=image.height)

    # ---------- write ----------
    def write(self, text: str) -> None:
        if not self._open():
            log.warning("clipboard locked by another process; could not set it")
            return
        try:
            self._user32.EmptyClipboard()
            data = text.encode("utf-16-le") + b"\x00\x00"
            handle = self._kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                return
            locked = self._kernel32.GlobalLock(handle)
            ctypes.memmove(locked, data, len(data))
            self._kernel32.GlobalUnlock(handle)
            self._user32.SetClipboardData(CF_UNICODETEXT, handle)
        finally:
            self._user32.CloseClipboard()
        self._last_seq = self._user32.GetClipboardSequenceNumber()

    # ---------- foreground window ----------
    def foreground(self) -> tuple[str, str]:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return "", ""
        length = self._user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return self._process_name(pid.value), buffer.value

    def _process_name(self, pid: int) -> str:
        if not pid:
            return ""
        if pid in self._proc_names:
            return self._proc_names[pid]
        handle = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        name = ""
        if handle:
            try:
                size = wintypes.DWORD(260)
                buffer = ctypes.create_unicode_buffer(260)
                if self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    name = buffer.value.rsplit("\\", 1)[-1]
                    if name.lower().endswith(".exe"):
                        name = name[:-4]
            finally:
                self._kernel32.CloseHandle(handle)
        if len(self._proc_names) > 512:
            self._proc_names.clear()
        self._proc_names[pid] = name
        return name
