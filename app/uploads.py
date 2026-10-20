"""Bounded receipt uploads. CEKBAO keeps metadata only (name, type, size, hash).

The file content is inspected for type and active content, then discarded.
CEKBAO does not read receipt text or images to decide settlement.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

_ALLOWED = {
    ".pdf": (b"%PDF-", "application/pdf"),
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".txt": (None, "text/plain"),
}
_DANGEROUS_INNER = {".exe", ".js", ".bat", ".cmd", ".sh", ".scr", ".html", ".htm", ".svg", ".php", ".ps1", ".jar",
                    ".msi", ".vbs", ".apk", ".dll"}
_PDF_ACTIVE = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA")


class UploadRejected(ValueError):
    pass


@dataclass(frozen=True)
class UploadMeta:
    safe_name: str
    media_type: str
    size: int
    sha256: str


def safe_filename(name: str | None) -> str:
    if not name:
        raise UploadRejected("file name is required")
    name = unicodedata.normalize("NFKC", name)
    name = re.split(r"[\\/]", name)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    name = re.sub(r"_+", "_", name)
    if not name or "." not in name:
        raise UploadRejected("file name needs an allowed extension")
    parts = name.lower().split(".")
    if any("." + p in _DANGEROUS_INNER for p in parts[1:-1]):
        raise UploadRejected("double extension with an executable or script type")
    return name[:80]


def inspect_upload(filename: str | None, data: bytes, max_bytes: int) -> UploadMeta:
    safe = safe_filename(filename)
    ext = "." + safe.lower().rsplit(".", 1)[-1]
    if ext not in _ALLOWED:
        raise UploadRejected(f"file type {ext} is not allowed (pdf, png, jpg, txt)")
    if len(data) == 0:
        raise UploadRejected("file is empty")
    if len(data) > max_bytes:
        raise UploadRejected(f"file is larger than {max_bytes} bytes")
    magic, media_type = _ALLOWED[ext]
    if magic is not None and not data.startswith(magic):
        raise UploadRejected("file content does not match its extension")
    if ext == ".pdf" and any(tok in data for tok in _PDF_ACTIVE):
        raise UploadRejected("PDF contains active content (JavaScript, launch action or embedded file)")
    if ext == ".txt":
        if b"\x00" in data:
            raise UploadRejected("text file contains binary data")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise UploadRejected("text file is not UTF-8") from None
    return UploadMeta(safe_name=safe, media_type=media_type, size=len(data), sha256=hashlib.sha256(data).hexdigest())
