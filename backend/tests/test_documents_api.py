from pathlib import Path

import pytest

from app.ingest import pipeline


class FakeProvider:
    name = "fake_provider"
    model = "fake-model"

    def __init__(self, outcome):
        self.outcome = outcome

    def extract(self, file_path: Path):
        return self.outcome


@pytest.fixture
def fake_chain(monkeypatch):
    def _set(providers):
        monkeypatch.setattr(pipeline, "get_provider_chain", lambda: providers)

    return _set


def _make_document(tmp_path, fake_chain, **overrides):
    result = {
        "correspondent": "Test Correspondent",
        "doc_type": "invoice",
        "doc_date": "2026-01-01",
        "expiry_date": "2026-12-31",
        "amount_raw": "10.00 EUR",
        "summary": "Summary",
        "full_text": None,
        "evidence": [],
        "raw_response": "{}",
        "cost_usd": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    result.update(overrides)
    fake_chain([FakeProvider(result)])
    src = tmp_path / f"{result['correspondent']}.txt"
    src.write_text("document body")
    return pipeline.process(src, source="upload")


def test_delete_removes_file_from_disk(tmp_path, fake_chain, client, admin_session, csrf_headers):
    """GDPR: deleting a document must remove the archived file, not just the
    database row -- otherwise "delete anytime" isn't actually true."""
    outcome = _make_document(tmp_path, fake_chain)
    doc_id = outcome["document_id"]

    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 200
    stored_path = Path(get_res.json()["stored_path"])
    assert stored_path.is_file()

    delete_res = client.delete(f"/api/documents/{doc_id}", headers=csrf_headers)
    assert delete_res.status_code == 200
    assert not stored_path.exists(), "the archived file must be gone from disk after delete"

    assert client.get(f"/api/documents/{doc_id}").status_code == 404


def test_delete_requires_csrf_token(tmp_path, fake_chain, client, admin_session):
    outcome = _make_document(tmp_path, fake_chain)
    doc_id = outcome["document_id"]

    res = client.delete(f"/api/documents/{doc_id}")
    assert res.status_code == 403


def test_expiry_dismissal_roundtrip(tmp_path, fake_chain, client, admin_session, csrf_headers):
    outcome = _make_document(tmp_path, fake_chain)
    doc_id = outcome["document_id"]

    dismiss_res = client.post(f"/api/documents/{doc_id}/expiry-dismissal", headers=csrf_headers)
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["expiry_dismissed_at"] is not None

    expiring = client.get("/api/documents/expiring").json()
    assert all(d["id"] != doc_id for d in expiring), "a dismissed document must not show up as expiring"

    restore_res = client.delete(f"/api/documents/{doc_id}/expiry-dismissal", headers=csrf_headers)
    assert restore_res.status_code == 200
    assert restore_res.json()["expiry_dismissed_at"] is None


def test_review_status_transition(tmp_path, fake_chain, client, admin_session, csrf_headers):
    outcome = _make_document(tmp_path, fake_chain)
    doc_id = outcome["document_id"]

    res = client.post(
        f"/api/documents/{doc_id}/review-status",
        json={"review_status": "zaplatit"},
        headers=csrf_headers,
    )
    assert res.status_code == 200
    assert res.json()["review_status"] == "zaplatit"


def test_review_status_rejects_unknown_value(tmp_path, fake_chain, client, admin_session, csrf_headers):
    outcome = _make_document(tmp_path, fake_chain)
    doc_id = outcome["document_id"]

    res = client.post(
        f"/api/documents/{doc_id}/review-status",
        json={"review_status": "not_a_real_status"},
        headers=csrf_headers,
    )
    assert res.status_code == 422
