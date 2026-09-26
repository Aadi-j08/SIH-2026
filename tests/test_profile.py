"""Phase B: provider profile CRUD and council verification, tenant-scoped."""
from app import cooperative as coop_mod
from app.cooperative import create_cooperative


def _worker_id(worker):
    return worker.user["worker_id"]


def test_worker_can_add_and_list_skills(worker):
    wid = _worker_id(worker)
    r = worker.post(f"/workers/{wid}/skills", json={"name": "tile", "level": "expert"})
    assert r.status_code == 201, r.text
    skill_id = r.json()["id"]

    r2 = worker.get(f"/workers/{wid}/skills")
    assert r2.status_code == 200
    names = {s["name"] for s in r2.json()}
    assert "tile" in names

    r3 = worker.patch(f"/workers/{wid}/skills/{skill_id}", json={"name": "tiling", "level": "intermediate"})
    assert r3.status_code == 200 and r3.json()["name"] == "tiling"

    r4 = worker.delete(f"/workers/{wid}/skills/{skill_id}")
    assert r4.status_code == 204
    assert not any(s["name"] == "tiling" for s in worker.get(f"/workers/{wid}/skills").json())


def test_worker_can_add_cert_and_portfolio_docs(worker):
    wid = _worker_id(worker)
    cert = worker.post(f"/workers/{wid}/certifications", json={
        "name": "Plumbing License", "issuing_org": "Municipal Corp",
        "issue_date": "2023-01-01", "document": "uploads/cert.pdf",
    }).json()
    assert cert["name"] == "Plumbing License"

    port = worker.post(f"/workers/{wid}/portfolio", json={
        "image_url": "uploads/before.jpg", "caption": "old tap", "category": "before",
    }).json()
    assert port["image_url"] == "uploads/before.jpg"

    doc = worker.post(f"/workers/{wid}/documents", json={
        "document_type": "id_proof", "file_url": "uploads/aadhaar.jpg",
    }).json()
    assert doc["document_type"] == "id_proof"

    summ = worker.get(f"/workers/{wid}/profile").json()
    assert cert["id"] in {c["id"] for c in summ["certifications"]}
    assert port["id"] in {p["id"] for p in summ["portfolio"]}
    assert doc["id"] in {d["id"] for d in summ["documents"]}
    assert 0 < summ["completeness"] <= 1


def test_worker_cannot_edit_another_workers_profile(worker, make_client):
    other = make_client("worker", name="Other Worker", phone="9200000001")
    other_id = other.user["worker_id"]
    r = worker.post(f"/workers/{other_id}/skills", json={"name": "carpentry"})
    assert r.status_code == 403


def test_council_verifies_certificate(council, worker):
    wid = _worker_id(worker)
    cert = worker.post(f"/workers/{wid}/certifications", json={"name": "License"}).json()
    r = council.post(f"/workers/{wid}/verify/certifications/{cert['id']}", json={"verified": True})
    assert r.status_code == 200
    assert r.json()["verified"] is True
    # verification flag reflected on the certificate
    got = council.get(f"/workers/{wid}/certifications").json()
    assert any(c["id"] == cert["id"] and c["verified"] for c in got)


def test_profile_is_tenant_scoped(worker, client, db_path):
    # A second cooperative must not see the worker's profile items.
    indore = create_cooperative(name="Indore Coop", code="SABHA-IN-999", region="Indore")
    wid = _worker_id(worker)
    # The worker exists in tenant 1; asking the API to act as Indore is a 403 for the user.
    r = worker.get(f"/workers/{wid}/profile", headers={"X-Cooperative-Id": str(indore.id)})
    assert r.status_code == 403


def test_council_cannot_activate_worker_without_aadhaar(council, make_client):
    pending = make_client("worker", name="Unverified Worker", phone="9200000002", trade="plumbing")
    wid = pending.user["worker_id"]
    # Council tries to activate without Aadhaar uploaded -> 409
    r = council.post(f"/workers/{wid}/approve", json={"status": "active"})
    assert r.status_code == 409, r.text
    assert "Aadhaar" in r.json()["detail"]
    # Worker uploads an Aadhaar document
    doc = pending.post(f"/workers/{wid}/documents", json={"document_type": "aadhaar", "file_url": "uploads/aadhaar.jpg"}).json()
    assert doc["document_type"] == "aadhaar"
    # Now council can activate
    r2 = council.post(f"/workers/{wid}/approve", json={"status": "active"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "active"
    # ...and the worker's /me reports active
    me = pending.get("/auth/me").json()["user"]
    assert me["worker_status"] == "active"
