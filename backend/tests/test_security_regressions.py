"""Regression tests for the 2026-07-28 security audit.

Each test here maps to a finding that was actually exploitable (or actually
crashed) before the fix, so they are written to fail loudly if the fix is ever
reverted -- not just to exercise the happy path.
"""

import asyncio
import time
from pathlib import Path

import pytest

from app.api.modules import upload as upload_module
from app.api.modules.documents import INLINE_SAFE_MIME_TYPES
from app.archive import store
from app.config import settings
from app.ingest import pipeline


class FakeProvider:
    name = "fake_provider"
    model = "fake-model"

    def __init__(self, outcome):
        self.outcome = outcome

    def extract(self, file_path: Path):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def fake_chain(monkeypatch):
    def _set(providers):
        monkeypatch.setattr(pipeline, "get_provider_chain", lambda: providers)

    return _set


def _result(**overrides):
    base = {
        "correspondent": "Acme Corp",
        "doc_type": "invoice",
        "doc_date": "2026-01-01",
        "expiry_date": None,
        "amount_raw": "10.00 EUR",
        "summary": "Summary",
        "full_text": None,
        "evidence": [],
        "raw_response": "{}",
        "cost_usd": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    base.update(overrides)
    return base


def _ingest(tmp_path, fake_chain, filename, content, **overrides):
    fake_chain([FakeProvider(_result(**overrides))])
    src = tmp_path / filename
    src.write_text(content)
    return pipeline.process(src, source="upload")


# --- Finding: stored XSS via inline document rendering (CRITICAL) -----------


@pytest.mark.parametrize(
    "filename, payload",
    [
        ("evil.html", "<script>fetch('/api/documents/export?format=json')</script>"),
        ("evil.svg", '<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>'),
    ],
)
def test_script_capable_documents_are_never_served_inline(
    tmp_path, fake_chain, client, admin_session, filename, payload
):
    """An HTML mail body (archived verbatim by the IMAP poller) or an uploaded
    SVG must download, never render on Muninn's origin -- rendering gave the
    document script execution against the app, and the CSRF cookie is
    intentionally readable by JS."""
    outcome = _ingest(tmp_path, fake_chain, filename, payload)

    res = client.get(f"/api/documents/{outcome['document_id']}/file")
    assert res.status_code == 200
    assert res.headers["content-disposition"].startswith("attachment"), (
        f"{filename} must be served as an attachment, got "
        f"{res.headers['content-disposition']!r}"
    )
    # Belt-and-braces: a sandboxed CSP means even a browser that ignored the
    # disposition gets an opaque origin with no scripts.
    assert "sandbox" in res.headers.get("content-security-policy", "")


def test_inline_allowlist_excludes_script_capable_types():
    for mime in ("text/html", "image/svg+xml", "application/xhtml+xml", "text/xml"):
        assert mime not in INLINE_SAFE_MIME_TYPES


def test_pdfs_still_render_inline(tmp_path, fake_chain, client, admin_session):
    """The fix must not break the actual use case: viewing an archived
    invoice in the browser."""
    outcome = _ingest(tmp_path, fake_chain, "invoice.pdf", "%PDF-1.4 fake")

    res = client.get(f"/api/documents/{outcome['document_id']}/file")
    assert res.headers["content-disposition"].startswith("inline")


def test_download_flag_still_forces_attachment(tmp_path, fake_chain, client, admin_session):
    outcome = _ingest(tmp_path, fake_chain, "invoice.pdf", "%PDF-1.4 fake")

    res = client.get(f"/api/documents/{outcome['document_id']}/file?download=true")
    assert res.headers["content-disposition"].startswith("attachment")


def test_app_pages_carry_a_content_security_policy(client):
    res = client.get("/api/health")
    csp = res.headers.get("content-security-policy", "")
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp


# --- Finding: AI-controlled path traversal on save (HIGH) -------------------


@pytest.mark.parametrize(
    "malicious_date",
    [
        "../../frontend/dist/x",
        "../../../etc/cron.d/x",
        "..",
        "/absolute/elsewhere",
    ],
)
def test_ai_supplied_doc_date_cannot_escape_the_archive(tmp_path, fake_chain, malicious_date):
    """doc_date comes out of the AI's JSON, i.e. out of content an attacker can
    influence via prompt injection, and went into the archive filename raw.
    A date of '../../frontend/dist/x' reproducibly wrote the document into the
    directory the SPA fallback serves from -- chaining prompt injection into
    the stored-XSS finding above."""
    outcome = _ingest(
        tmp_path, fake_chain, "doc.txt", "body", doc_date=malicious_date
    )

    from app.api.modules.documents import get_document

    stored = Path(get_document(outcome["document_id"])["stored_path"]).resolve()
    assert stored.is_relative_to(settings.archive_dir.resolve()), (
        f"document escaped the archive: {stored}"
    )
    assert ".." not in stored.parts


def test_correspondent_and_doc_type_are_still_slugified(tmp_path, fake_chain):
    outcome = _ingest(
        tmp_path,
        fake_chain,
        "doc.txt",
        "body",
        correspondent="../../etc",
        doc_type="../../passwd",
        doc_date="2026-02-03",
    )

    from app.api.modules.documents import get_document

    stored = Path(get_document(outcome["document_id"])["stored_path"]).resolve()
    assert stored.is_relative_to(settings.archive_dir.resolve())


def test_slugify_date_keeps_well_formed_dates_verbatim():
    assert store._slugify_date("2026-01-31") == "2026-01-31"
    # ...and reduces anything else to one safe component instead of dropping it
    assert "/" not in store._slugify_date("../../x")
    assert ".." not in store._slugify_date("../../x")


def test_assert_inside_archive_rejects_escapes():
    with pytest.raises(ValueError):
        store._assert_inside_archive(settings.archive_dir / ".." / "escaped.pdf")


# --- Finding: blocking AI subprocess in an async route (HIGH) ---------------


def test_upload_route_does_not_block_the_event_loop(monkeypatch):
    """pipeline.process() shells out to the claude/codex CLIs with a 120s
    timeout per provider. Awaited directly from an async def route it ran ON
    the event loop and froze every other request, the mail poller and the
    retry queue for its whole duration."""
    import threading

    started = threading.Event()
    release = threading.Event()

    def blocking_process(file_path, source, source_detail=None):
        started.set()
        # Stands in for subprocess.run(timeout=120) x3 providers.
        release.wait(10)
        return {"document_id": 1, "duplicate": False, "status": "processed"}

    monkeypatch.setattr(upload_module.pipeline, "process", blocking_process)
    monkeypatch.setattr(
        upload_module, "_stage_upload", lambda file, dest: dest.write_bytes(b"x")
    )

    class _FakeUpload:
        filename = "scan.pdf"
        file = None

    async def scenario():
        task = asyncio.create_task(upload_module.upload(_FakeUpload()))

        # Wait until the "AI call" is definitely in flight. Reaching this
        # point at all proves the event loop kept running while it was: with
        # the old direct call, the loop could not schedule these sleeps until
        # blocking_process() had already returned.
        deadline = time.monotonic() + 5
        while not started.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        assert started.is_set(), "the AI call never started"

        # The decisive assertion: the call is still running (release is not
        # set) AND we are executing on the event loop. If process() ran on
        # the loop, we would only get here after it finished, and the upload
        # task would already be done.
        assert not release.is_set()
        assert not task.done(), (
            "the event loop only regained control after the AI call finished -- "
            "pipeline.process() is blocking the loop again"
        )

        release.set()
        return await task

    result = asyncio.run(scenario())
    assert result["status"] == "processed"


def test_upload_routes_are_coroutines():
    assert asyncio.iscoroutinefunction(upload_module.upload)
    assert asyncio.iscoroutinefunction(upload_module.upload_combine)


# --- Finding: no size/type limit on the single-file upload path ------------


def test_upload_rejects_unsupported_extension(client, admin_session, csrf_headers):
    res = client.post(
        "/api/upload",
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
        headers=csrf_headers,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "upload_unsupported_format"


def test_upload_rejects_oversized_file(monkeypatch, client, admin_session, csrf_headers):
    monkeypatch.setattr(upload_module.settings, "max_upload_mb", 0.0001)
    res = client.post(
        "/api/upload",
        files={"file": ("big.pdf", b"x" * 5000, "application/pdf")},
        headers=csrf_headers,
    )
    assert res.status_code == 413
    assert res.json()["detail"]["code"] == "upload_too_large"


def test_failed_upload_leaves_no_temp_directory(monkeypatch, client, admin_session, csrf_headers):
    """A crash between staging and archiving used to leave the document (a
    payslip, a contract) in /tmp forever, outside the app's delete flow."""
    import tempfile

    created: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def tracking_mkdtemp(*args, **kwargs):
        path = real_mkdtemp(*args, **kwargs)
        created.append(Path(path))
        return path

    monkeypatch.setattr(upload_module.tempfile, "mkdtemp", tracking_mkdtemp)

    def exploding_process(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(upload_module.pipeline, "process", exploding_process)

    with pytest.raises(ValueError):
        client.post(
            "/api/upload",
            files={"file": ("payslip.pdf", b"secret", "application/pdf")},
            headers=csrf_headers,
        )

    assert created, "the upload never staged anything"
    for path in created:
        assert not path.exists(), f"temp dir with a sensitive document leaked: {path}"


# --- Finding: search 500s on ordinary queries ------------------------------


@pytest.mark.parametrize(
    "query",
    ["T-Mobile", "it's", '"', "uniqa OR", "*", "NEAR(", "a AND", "-", "()"],
)
def test_search_never_500s_on_fts5_syntax(tmp_path, fake_chain, client, admin_session, query):
    """The search box fires on every keystroke and Slovak correspondent names
    are full of hyphens, so raw FTS5 syntax errors were a routine 500."""
    _ingest(tmp_path, fake_chain, "doc.txt", "T-Mobile invoice body")

    res = client.get("/api/documents", params={"q": query})
    assert res.status_code == 200, f"query {query!r} returned {res.status_code}: {res.text}"


def test_search_still_finds_hyphenated_correspondents(tmp_path, fake_chain, client, admin_session):
    _ingest(tmp_path, fake_chain, "doc.txt", "body", correspondent="T-Mobile")

    rows = client.get("/api/documents", params={"q": "T-Mobile"}).json()
    assert [r["correspondent"] for r in rows] == ["T-Mobile"]


# --- Finding: list/export shipped every document's full text ---------------


def test_list_response_omits_full_text_and_raw_ai_response(
    tmp_path, fake_chain, client, admin_session
):
    _ingest(tmp_path, fake_chain, "doc.txt", "a very long transcription " * 100)

    rows = client.get("/api/documents").json()
    assert rows and "full_text" not in rows[0] and "ai_raw_response" not in rows[0]

    # The single-document view still returns them.
    detail = client.get(f"/api/documents/{rows[0]['id']}").json()
    assert "full_text" in detail and "ai_raw_response" in detail


# --- Finding: deletion left no audit trail / bulk delete was not atomic ----


def test_delete_is_recorded_in_the_deletion_log(tmp_path, fake_chain, client, admin_session, csrf_headers):
    from app.db import execute

    outcome = _ingest(tmp_path, fake_chain, "doc.txt", "body")
    doc_id = outcome["document_id"]

    assert client.delete(f"/api/documents/{doc_id}", headers=csrf_headers).status_code == 200

    row = execute(
        "SELECT * FROM document_deletions WHERE document_id = ?", (doc_id,)
    ).fetchone()
    assert row is not None, "deleting a document must leave an audit record"
    assert row["actor"] == "admin"
    assert row["file_removed"] == 1


def test_bulk_delete_removes_rows_even_when_one_file_is_missing(
    tmp_path, fake_chain, client, admin_session, csrf_headers
):
    """One bad stored_path used to abort the request before the DELETE ran:
    the already-unlinked files were gone and every DB row survived."""
    from app.db import execute

    first = _ingest(tmp_path, fake_chain, "one.txt", "body one")["document_id"]
    second = _ingest(tmp_path, fake_chain, "two.txt", "body two")["document_id"]

    # Make the first one's stored_path a directory -> _delete_stored_file
    # raises the 409 that previously aborted the whole batch.
    broken_dir = settings.archive_dir / "broken-stored-path"
    broken_dir.mkdir(exist_ok=True)
    execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(broken_dir), first))

    res = client.delete("/api/documents", params={"ids": f"{first},{second}"}, headers=csrf_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["deleted"] == 2, "both rows must be gone regardless of the file error"
    assert [e["id"] for e in body["file_errors"]] == [first]
    assert client.get(f"/api/documents/{second}").status_code == 404


# --- Finding: watch folder accepted any directory --------------------------


def test_watch_folder_rejects_app_storage_and_broad_roots(client, admin_session, csrf_headers):
    res = client.post(
        "/api/settings/watch-folders",
        json={"path": str(settings.archive_dir)},
        headers=csrf_headers,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "folder_is_app_storage"

    res = client.post(
        "/api/settings/watch-folders", json={"path": "/home"}, headers=csrf_headers
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "folder_too_broad"

    res = client.post(
        "/api/settings/watch-folders", json={"path": "relative/path"}, headers=csrf_headers
    )
    assert res.status_code == 422


def test_watch_folder_requires_confirmation_when_not_empty(
    tmp_path, monkeypatch, client, admin_session, csrf_headers
):
    """Registering a folder sweeps everything already in it to the AI and
    physically moves it into the archive. A typo one path segment short must
    not do that silently."""
    # Stub the sweep itself: this test is about the confirmation gate, and
    # actually starting observers would hand a real file to whatever AI
    # provider happens to be installed on the machine running the tests.
    from app.api.modules import settings as settings_module

    monkeypatch.setattr(settings_module, "sync_watch_folders", lambda: None)

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "tax-return.pdf").write_text("important")

    res = client.post(
        "/api/settings/watch-folders", json={"path": str(inbox)}, headers=csrf_headers
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "folder_not_empty"
    assert (inbox / "tax-return.pdf").exists(), "nothing may be touched before confirmation"

    res = client.post(
        "/api/settings/watch-folders",
        json={"path": str(inbox), "confirm_existing": True},
        headers=csrf_headers,
    )
    assert res.status_code == 200
    assert str(inbox.resolve()) in res.json()["folders"]

    client.delete(
        "/api/settings/watch-folders",
        params={"path": str(inbox.resolve())},
        headers=csrf_headers,
    )


# --- Finding: unbounded thread fan-out from the watch folder ---------------


def test_watch_folder_uses_a_bounded_worker_pool():
    from app.ingest import watch_folder

    assert watch_folder._executor._max_workers == watch_folder.MAX_CONCURRENT_INGESTS
    assert watch_folder.MAX_CONCURRENT_INGESTS <= 4


# --- Finding: a provider exception escaped the whole ingest ----------------


def test_unexpected_provider_exception_does_not_kill_the_ingest(tmp_path, fake_chain):
    """A truncated Anthropic response raised JSONDecodeError, which is not an
    ExtractionError -- it escaped pipeline.process() as an unhandled 500 with
    no document row and no parked file."""
    import json as _json

    fake_chain([FakeProvider(_json.JSONDecodeError("Expecting value", "{", 0))])
    src = tmp_path / "truncated.txt"
    src.write_text("content")

    result = pipeline.process(src, source="upload")
    assert result["status"] == "failed"
    assert result["document_id"] is not None
