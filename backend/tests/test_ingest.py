from pathlib import Path

import pytest

from app.ai_engine.base import ExtractionError, ProviderUnavailableError
from app.ingest import pipeline


class FakeProvider:
    """A minimal AIProvider test double. `outcome` controls what extract()
    does: a dict result on success, or an exception instance to raise."""

    name = "fake_provider"
    model = "fake-model"

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    def extract(self, file_path: Path):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _result(**overrides):
    base = {
        "correspondent": "Acme Corp",
        "doc_type": "invoice",
        "doc_date": "2026-01-01",
        "expiry_date": None,
        "amount_raw": "42.00 EUR",
        "summary": "Test invoice",
        "full_text": None,
        "evidence": [],
        "raw_response": "{}",
        "cost_usd": 0.001,
        "input_tokens": 10,
        "output_tokens": 5,
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_chain(monkeypatch):
    """Patch the provider chain used by pipeline.py. Call with a list of
    FakeProvider instances (tried in order, exactly like the real chain)."""

    def _set(providers):
        monkeypatch.setattr(pipeline, "get_provider_chain", lambda: providers)

    return _set


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def test_successful_ingest_creates_processed_document(tmp_path, fake_chain):
    provider = FakeProvider(_result(correspondent="Acme Cloud", amount_raw="89.00 EUR"))
    fake_chain([provider])

    src = _write(tmp_path, "invoice.txt", "invoice body")
    result = pipeline.process(src, source="upload")

    assert result["status"] == "processed"
    assert result["duplicate"] is False
    assert provider.calls == 1


def test_duplicate_file_skips_ai_call(tmp_path, fake_chain):
    provider = FakeProvider(_result())
    fake_chain([provider])

    first = _write(tmp_path, "one.txt", "same content")
    pipeline.process(first, source="upload")
    assert provider.calls == 1

    second = _write(tmp_path, "two.txt", "same content")
    result = pipeline.process(second, source="upload")

    assert result["duplicate"] is True
    assert provider.calls == 1, "a byte-identical file must not trigger a second AI call"


def test_all_providers_unavailable_lands_as_pending(tmp_path, fake_chain):
    fake_chain(
        [
            FakeProvider(ProviderUnavailableError("rate limited")),
            FakeProvider(ProviderUnavailableError("auth failed")),
        ]
    )

    src = _write(tmp_path, "outage.txt", "whatever content")
    result = pipeline.process(src, source="upload")

    assert result["status"] == "pending"


def test_genuine_content_failure_lands_as_failed(tmp_path, fake_chain):
    fake_chain([FakeProvider(ExtractionError("could not parse the model's response"))])

    src = _write(tmp_path, "broken.txt", "garbage")
    result = pipeline.process(src, source="upload")

    assert result["status"] == "failed"


def test_mixed_outcome_prefers_failed_over_pending(tmp_path, fake_chain):
    """If at least one provider genuinely tried and rejected the content
    (not just an availability problem), the document should not be queued
    for silent automatic retry -- something about it needs a human look."""
    fake_chain(
        [
            FakeProvider(ProviderUnavailableError("rate limited")),
            FakeProvider(ExtractionError("unreadable document")),
        ]
    )

    src = _write(tmp_path, "mixed.txt", "content")
    result = pipeline.process(src, source="upload")

    assert result["status"] == "failed"


def test_reprocess_pending_document_updates_in_place(tmp_path, fake_chain):
    fake_chain([FakeProvider(ProviderUnavailableError("down"))])
    src = _write(tmp_path, "queued.txt", "queued content")
    first = pipeline.process(src, source="upload")
    assert first["status"] == "pending"

    fake_chain([FakeProvider(_result(correspondent="Now Available Inc"))])
    second = pipeline.reprocess_document(first["document_id"])

    assert second["status"] == "processed"
    assert second["document_id"] == first["document_id"], "must update the same row, not insert a new one"
