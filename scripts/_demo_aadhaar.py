"""
A small, genuinely valid one-page PDF standing in for a scanned Aadhaar.

Shared by both demo seeders. Uploads live in the database (BYTEA on Postgres,
BLOB on SQLite), so a seeded document has to carry real content -- a file_url on
its own resolves to nothing and the council's preview answers 404 on the exact
queue the verification screen exists to act on.

Built by hand to keep the repository free of binary fixtures. A correct xref
table is included because the council opens these in the browser's PDF viewer.
"""
from __future__ import annotations

import hashlib


def aadhaar_pdf(name: str, phone: str) -> bytes:
    """Return PDF bytes naming `name`, with the last four digits of `phone`."""
    lines = [
        b"Government of India  |  Unique Identification Authority of India",
        b"",
        f"Aadhaar number  XXXX XXXX {phone[-4:]}".encode("ascii", "replace"),
        f"Name  {name}".encode("ascii", "replace"),
        b"Date of birth  01/01/1994",
        b"Address  Bhopal, Madhya Pradesh",
        b"",
        b"DEMO DOCUMENT - seeded for the council verification walkthrough",
    ]
    text = "BT /F1 11 Tf 24 200 Td 16 TL\n" + "\n".join(
        f"({line.decode('ascii').replace(chr(40), '').replace(chr(41), '')}) Tj T*"
        for line in lines
    ) + "\nET"
    content = text.encode("ascii")

    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 420 260]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def aadhaar_document(name: str, phone: str) -> tuple[str, str, int, bytes]:
    """The (file_url, filename, byte_size, content) a worker_documents row needs.

    file_url uses the same db:worker_documents/<digest> reference the upload path
    writes, so seeded rows are indistinguishable from uploaded ones.
    """
    pdf = aadhaar_pdf(name, phone)
    return (
        f"db:worker_documents/{hashlib.sha256(pdf).hexdigest()[:16]}",
        f"aadhaar-{phone}.pdf",
        len(pdf),
        pdf,
    )
