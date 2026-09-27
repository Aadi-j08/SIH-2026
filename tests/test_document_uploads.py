"""Worker document uploads: format and size validation, storage, and who may read them.

The rule under test throughout: the *bytes* decide what a document is, never the
browser-supplied Content-Type or the file extension. Both are attacker-controlled,
so a worker who renames a binary to .pdf must still be refused.
"""
import pytest

from app import uploads


def _worker_id(worker):
    return worker.user["worker_id"]


# Byte headers that must be recognised, with the extension each should carry.
PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n" + b"0" * 512
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 512
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 512
EXE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 512
GIF = b"GIF89a" + b"\x00" * 512
SCRIPT = b"#!/bin/sh\nrm -rf /\n" + b"\x00" * 512


def _upload(client, worker_id, name, data, content_type="application/octet-stream", document_type="aadhaar"):
    return client.post(
        f"/workers/{worker_id}/documents/upload",
        files={"file": (name, data, content_type)},
        data={"document_type": document_type},
    )


# ── accepted formats ──────────────────────────────────────────────────────

@pytest.mark.parametrize("name,data,expected", [
    ("aadhaar.pdf", PDF, "application/pdf"),
    ("aadhaar.PNG", PNG, "image/png"),
    ("scan.jpg", JPEG, "image/jpeg"),
    ("scan.jpeg", JPEG, "image/jpeg"),
])
def test_accepts_pdf_jpg_png(make_client, name, data, expected):
    w = make_client("worker")
    r = _upload(w, _worker_id(w), name, data)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["content_type"] == expected
    assert body["byte_size"] == len(data)
    assert body["has_content"] is True
    # The filename is echoed back so the UI can label the document.
    assert body["filename"].lower().endswith(name[name.rfind("."):].lower())


def test_accepts_a_handed_unicode_filename(make_client):
    w = make_client("worker")
    r = _upload(w, _worker_id(w), "आधार कार्ड.pdf", PDF)
    assert r.status_code == 201, r.text
    # Non-ASCII is transliterated/stripped to something safe to serve back.
    assert r.json()["filename"].isascii()


# ── refused formats: judged on content, not on the claim ──────────────────

@pytest.mark.parametrize("name,data", [
    ("aadhaar.pdf", EXE),        # a binary renamed to .pdf, claiming to be a PDF
    ("aadhaar.pdf", SCRIPT),     # a shell script renamed to .pdf
    ("photo.png", GIF),          # a GIF is not in the accepted set
    ("aadhaar.txt", PDF),        # real PDF bytes behind a non-document extension
    ("aadhaar.jpg", PNG),        # PNG bytes behind a .jpg name
    ("aadhaar.pdf", b""),        # empty file
])
def test_rejects_bytes_that_are_not_an_accepted_document(make_client, name, data):
    w = make_client("worker")
    r = _upload(w, _worker_id(w), name, data, content_type="application/pdf")
    assert r.status_code == 415, r.text
    # The message is written for the worker, not for a developer.
    detail = r.json()["detail"]
    assert detail and "Traceback" not in detail
    assert not w.get(f"/workers/{_worker_id(w)}/documents").json(), "nothing may be stored on rejection"


def test_rejection_message_never_echoes_the_stored_content(make_client):
    w = make_client("worker")
    r = _upload(w, _worker_id(w), "aadhaar.pdf", SCRIPT, content_type="application/pdf")
    assert r.status_code == 415
    assert "rm -rf" not in r.json()["detail"]


def test_lying_content_type_does_not_get_through(make_client):
    """A client may claim whatever it likes; only the bytes are judged."""
    w = make_client("worker")
    r = _upload(w, _worker_id(w), "harmless.pdf", SCRIPT, content_type="application/pdf")
    assert r.status_code == 415


# ── size limit ────────────────────────────────────────────────────────────

def test_rejects_file_over_the_size_limit(make_client, monkeypatch):
    monkeypatch.setenv("SAHAKARSETU_UPLOAD_MAX_BYTES", "2048")
    w = make_client("worker")
    r = _upload(w, _worker_id(w), "aadhaar.pdf", PDF + b"0" * 4096, content_type="application/pdf")
    assert r.status_code == 415, r.text
    # The message names the real limit rather than rounding it to "0.0 MB".
    assert "2 KB" in r.json()["detail"]


def test_accepts_a_file_exactly_at_the_limit(make_client, monkeypatch):
    monkeypatch.setenv("SAHAKARSETU_UPLOAD_MAX_BYTES", str(len(PDF)))
    w = make_client("worker")
    assert _upload(w, _worker_id(w), "aadhaar.pdf", PDF, content_type="application/pdf").status_code == 201


def test_size_limit_must_be_reached_before_the_extension_rule(make_client, monkeypatch):
    """A too-large file is reported as too large, not as a bad format."""
    monkeypatch.setenv("SAHAKARSETU_UPLOAD_MAX_BYTES", "16")
    w = make_client("worker")
    detail = _upload(w, _worker_id(w), "aadhaar.pdf", PDF, content_type="application/pdf").json()["detail"]
    assert "limit" in detail and "does not look like" not in detail


def test_oversize_message_reports_the_real_size_not_the_read_cap(make_client, monkeypatch):
    """The read is capped at the limit, so len(data) would report '5 MB' for a
    much larger file. The message must describe what the worker actually picked."""
    monkeypatch.setenv("SAHAKARSETU_UPLOAD_MAX_BYTES", str(1024 * 1024))
    w = make_client("worker")
    r = _upload(w, _worker_id(w), "aadhaar.pdf", PDF + b"0" * (12 * 1024 * 1024), content_type="application/pdf")
    assert r.status_code == 415, r.text
    detail = r.json()["detail"]
    assert "over the 1 MB limit" in detail
    assert "1.0 MB," not in detail.split("over")[0]   # not the capped read size


def test_describe_bytes_is_exact_for_odd_limits():
    assert uploads.describe_bytes(5 * 1024 * 1024) == "5 MB"
    assert uploads.describe_bytes(2048) == "2 KB"
    assert uploads.describe_bytes(1500) == "1 KB"
    assert uploads.describe_bytes(512) == "512 bytes"
    assert uploads.describe_bytes(3_000_000) == "2.9 MB"


# ── who may upload ────────────────────────────────────────────────────────

def test_worker_cannot_upload_to_another_worker(make_client):
    w = make_client("worker")
    other = make_client("worker", phone="9200000099", name="Someone Else")
    r = _upload(other, _worker_id(w), "aadhaar.pdf", PDF, content_type="application/pdf")
    assert r.status_code in (403, 404), r.text


def test_household_cannot_upload_a_document(make_client):
    from app.auth import require_worker
    c = make_client("customer")
    r = _upload(c, _worker_id(c), "aadhaar.pdf", PDF, content_type="application/pdf")
    assert r.status_code in (401, 403, 404, 422), r.text


def test_unknown_document_type_is_rejected(make_client):
    w = make_client("worker")
    r = _upload(w, _worker_id(w), "a.pdf", PDF, content_type="application/pdf", document_type="passport")
    assert r.status_code == 400, r.text


def test_per_worker_document_cap(make_client, monkeypatch):
    monkeypatch.setenv("SAHAKARSETU_UPLOAD_MAX_FILES", "1")
    w = make_client("worker")
    wid = _worker_id(w)
    assert _upload(w, wid, "a.pdf", PDF, content_type="application/pdf").status_code == 201
    r = _upload(w, wid, "b.pdf", PDF + b"%PDF-1.7\n", content_type="application/pdf")
    assert r.status_code == 409, r.text
    assert "at most 1 document" in r.json()["detail"]   # singular


# ── reading the bytes back ────────────────────────────────────────────────

def test_owner_can_download_and_bytes_match(make_client):
    w = make_client("worker")
    wid = _worker_id(w)
    doc_id = _upload(w, wid, "aadhaar.pdf", PDF, content_type="application/pdf").json()["id"]
    r = w.get(f"/documents/{doc_id}/file")
    assert r.status_code == 200
    assert r.content == PDF


def test_download_is_an_attachment_and_never_renders_inline(make_client):
    """Even if a stored file is of a type a browser might render, it must not run
    against the app's origin."""
    w = make_client("worker")
    doc_id = _upload(w, _worker_id(w), "a.png", PNG, content_type="image/png").json()["id"]
    r = w.get(f"/documents/{doc_id}/file")
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert "sandbox" in r.headers["content-security-policy"]


def test_council_can_read_the_document(make_client, council):
    w = make_client("worker")
    doc_id = _upload(w, _worker_id(w), "aadhaar.pdf", PDF, content_type="application/pdf").json()["id"]
    r = council.get(f"/documents/{doc_id}/file")
    assert r.status_code == 200 and r.content == PDF


def test_another_worker_cannot_read_the_document(make_client):
    w = make_client("worker")
    doc_id = _upload(w, _worker_id(w), "aadhaar.pdf", PDF, content_type="application/pdf").json()["id"]
    other = make_client("worker", phone="9200000098", name="Nosy")
    assert other.get(f"/documents/{doc_id}/file").status_code in (403, 404)


def test_url_only_document_has_no_bytes_to_download(make_client):
    """The older POST /workers/{id}/documents rows must keep working, and must 404
    cleanly on the file endpoint rather than serving something unexpected."""
    w = make_client("worker")
    wid = _worker_id(w)
    legacy = w.post(f"/workers/{wid}/documents", json={"document_type": "aadhaar", "file_url": "uploads/x.jpg"})
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["has_content"] is False
    assert w.get(f"/documents/{legacy.json()['id']}/file").status_code == 404


# ── the gate this exists to satisfy ───────────────────────────────────────

def test_a_verified_aadhaar_from_a_real_upload_unblocks_approval(make_client, council):
    """The whole point of the upload step: a worker can now reach activation."""
    from app.profile import has_aadhaar

    w = make_client("worker", approved=False)
    wid = _worker_id(w)
    assert w.get("/auth/me").json()["user"]["worker_status"] == "pending"
    assert council.post(f"/workers/{wid}/approve", json={"status": "active"}).status_code == 409

    doc_id = _upload(w, wid, "aadhaar.pdf", PDF, content_type="application/pdf").json()["id"]
    assert not has_aadhaar(wid), "an upload alone must not count as verified"
    assert council.post(f"/workers/{wid}/approve", json={"status": "active"}).status_code == 409

    assert council.post(f"/documents/{doc_id}/verify", json={"verified": True}).status_code == 200
    assert has_aadhaar(wid)
    approved = council.post(f"/workers/{wid}/approve", json={"status": "active"})
    assert approved.status_code == 200 and approved.json()["status"] == "active"


def test_uploading_a_second_aadhaar_does_not_leak_the_old_verification(make_client, council):
    w = make_client("worker", approved=False)
    wid = _worker_id(w)
    first = _upload(w, wid, "aadhaar.pdf", PDF, content_type="application/pdf").json()["id"]
    council.post(f"/documents/{first}/verify", json={"verified": True})

    # A corrected re-upload is a new document; it must be reviewed on its own merit.
    second = _upload(w, wid, "aadhaar-v2.pdf", PDF + b"%PDF-1.7\n", content_type="application/pdf")
    assert second.status_code == 201
    assert second.json()["id"] != first
    assert second.json()["verified"] is False


# ── the migration this feature depends on ──────────────────────────────────

def test_blob_migration_upgrades_a_pre_existing_database(tmp_path, monkeypatch):
    """worker_documents gained four columns additively. A database created before
    that migration must gain them without losing rows, and re-running must be a
    no-op — the project's rule is additive migrations, never a table rebuild."""
    import sqlite3

    from app import database

    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, portal TEXT NOT NULL,
                            name TEXT, phone TEXT, password_hash TEXT, locality TEXT,
                            role TEXT, worker_id INTEGER, cooperative_id INTEGER NOT NULL DEFAULT 1,
                            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE worker_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id INTEGER NOT NULL,
            document_type TEXT NOT NULL, file_url TEXT NOT NULL, uploaded_at TEXT,
            cooperative_id INTEGER NOT NULL DEFAULT 1,
            verified INTEGER NOT NULL DEFAULT 0, verified_by INTEGER, verified_at TEXT,
            rejection_reason TEXT, UNIQUE (worker_id, document_type, file_url)
        );
        CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY,
                                        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO worker_documents (worker_id, document_type, file_url)
            VALUES (7, 'aadhaar', 'uploads/legacy.jpg');
        INSERT INTO schema_migrations (version) VALUES (8);
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "DB_PATH", legacy)
    database.init_db()
    database.init_db()  # idempotent

    check = sqlite3.connect(legacy)
    columns = {row[1] for row in check.execute("PRAGMA table_info(worker_documents)")}
    assert {"content", "filename", "content_type", "byte_size"} <= columns
    # The pre-existing row and its reference survive untouched.
    assert check.execute("SELECT file_url FROM worker_documents WHERE worker_id=7").fetchone()[0] == "uploads/legacy.jpg"
    assert check.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=9").fetchone()[0] == 1
    check.close()
