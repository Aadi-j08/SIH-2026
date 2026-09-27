"""
Validation for worker-uploaded identity documents.

The uploaded bytes are what get judged, never the browser-supplied
Content-Type or the file extension — both are attacker-controlled. A file is
accepted only if its leading bytes match a known signature for PDF, JPEG or
PNG, its name carries an extension that agrees with that signature, and it is
within the size cap. Anything else is rejected with a reason the UI can show
the worker verbatim.

Config (env, matching the project's other names):
    SAHAKARSETU_UPLOAD_MAX_BYTES   hard size cap, default 5 MiB
    SAHAKARSETU_UPLOAD_MAX_FILES   documents one worker may hold, default 10
"""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_FILES = 10

# Magic bytes per accepted format. JPEG's SOI marker is only two bytes and is a
# common prefix, so it is paired with the stricter JFIF/Exif markers.
_SIGNATURES: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("application/pdf", (b"%PDF-",)),
    ("image/jpeg", (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xe2", b"\xff\xd8\xff\xdb")),
    ("image/png", (b"\x89PNG\r\n\x1a\n",)),
)

# Extension -> the content type that extension is allowed to carry. Keeps a
# renamed file (report.pdf.exe, or a .jpg that is really something else) out.
_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
_EXTENSION_FOR_TYPE = {v: k for k, v in _EXTENSIONS.items()}

# A Windows device name is a poor filename for every host that may serve these
# bytes back (a worker uploading CON.jpg breaks a Windows council laptop).
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]")
_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class UploadRejected(ValueError):
    """The upload was refused; `message` is safe to show the worker."""


def max_bytes() -> int:
    try:
        return int(os.environ.get("SAHAKARSETU_UPLOAD_MAX_BYTES", DEFAULT_MAX_BYTES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_BYTES


def max_files() -> int:
    try:
        return int(os.environ.get("SAHAKARSETU_UPLOAD_MAX_FILES", DEFAULT_MAX_FILES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_FILES


def describe_bytes(size: int) -> str:
    """Human-readable byte count, e.g. '5 MB', '500 KB', '1024 bytes'.

    Exact for any limit, including sub-megabyte ones, so the rejection message
    never reads '0.0 MB, over the 0.0 MB limit'.
    """
    if size >= 1024 * 1024 and size % (1024 * 1024) == 0:
        return f"{size // (1024 * 1024)} MB"
    if size >= 1024 and size % 1024 == 0:
        return f"{size // 1024} KB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} bytes"


def describe_limit() -> str:
    """The configured size cap as a string the worker can read."""
    return describe_bytes(max_bytes())


def sniff_content_type(head: bytes) -> str | None:
    """The content type implied by the file's leading bytes, or None if unknown."""
    for content_type, markers in _SIGNATURES:
        if any(head.startswith(marker) for marker in markers):
            return content_type
    return None


def accepted_extensions() -> list[str]:
    """The extension list for accept="" on a file input."""
    return sorted(_EXTENSIONS)


def safe_filename(name: str | None, fallback_ext: str) -> str:
    """A filename safe to store and to echo in a Content-Disposition header."""
    raw = unicodedata.normalize("NFKD", (name or "").strip())
    raw = raw.encode("ascii", "ignore").decode("ascii")
    stem, dot, ext = raw.rpartition(".")
    if not dot or not stem:
        stem, ext = raw, fallback_ext.lstrip(".")
    cleaned = _UNSAFE_FILENAME.sub("_", stem).strip(" .")
    if not cleaned:
        cleaned = "document"
    if cleaned.split(".")[0].lower() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return f"{cleaned[:60]}.{ext[:10]}"


def validate_upload(filename: str | None, data: bytes, declared_size: int | None = None) -> tuple[str, str, str]:
    """    Check a fully-read upload. Returns (safe_filename, content_type, file_url).

    The browser's Content-Type is deliberately not an argument: it is
    attacker-controlled, so it is never consulted.

    `declared_size` is the uploader's own Content-Length for the part. It is used
    only to phrase the oversize message — `data` is capped at the limit, so its
    length would otherwise report the cap ("5.0 MB") rather than the real size.

    Raises UploadRejected with a message meant for the worker.
    """
    if not data:
        raise UploadRejected("That file is empty. Choose it again and check it opens on your phone.")
    if len(data) > max_bytes():
        reported = declared_size if declared_size and declared_size > max_bytes() else len(data)
        raise UploadRejected(
            f"That file is {describe_bytes(reported)}, over the {describe_limit()} limit. "
            "Photograph the document again, or save it as a smaller PDF."
        )

    # The whole point: judge the bytes, not the claim made about them.
    detected = sniff_content_type(data[:16])
    if detected is None:
        raise UploadRejected(
            "That does not look like a PDF, JPG or PNG. Upload a photo of the document "
            "or a PDF — not a link, and not another kind of file."
        )

    safe = safe_filename(filename, _EXTENSION_FOR_TYPE[detected])
    actual_ext = _extension_of(safe)
    if actual_ext is None or _EXTENSIONS.get(actual_ext) != detected:
        allowed = ", ".join(sorted(e for e, t in _EXTENSIONS.items() if t == detected))
        raise UploadRejected(
            f"This file is really {detected}, but its name ends in "
            f"{actual_ext or 'nothing'}. Rename it so it ends in {allowed}."
        )

    # The digest keeps the storage reference unique per distinct file, which is
    # what the (worker_id, document_type, file_url) unique key needs: the same
    # photo uploaded twice is a genuine duplicate and should be refused, while a
    # corrected re-upload of the same name lands as a new document.
    digest = hashlib.sha256(data).hexdigest()[:16]
    return safe, detected, f"db:worker_documents/{digest}"


def _extension_of(filename: str) -> str | None:
    _, dot, ext = filename.rpartition(".")
    return f".{ext.lower()}" if dot and ext else None
