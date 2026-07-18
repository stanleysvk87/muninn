from pathlib import Path

import pytest

from app.api.modules.documents import list_documents
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


def test_search_matches_full_text_not_just_summary(tmp_path, fake_chain):
    """The whole point of full_text indexing: a word that only appears in
    the document body (not in the AI's short summary/correspondent/type)
    must still be findable."""
    fake_chain(
        [
            FakeProvider(
                {
                    "correspondent": "Some Company",
                    "doc_type": "invoice",
                    "doc_date": "2026-01-01",
                    "expiry_date": None,
                    "amount_raw": None,
                    "summary": "A short summary that never mentions the marker.",
                    "full_text": None,
                    "evidence": [],
                    "raw_response": "{}",
                    "cost_usd": None,
                    "input_tokens": None,
                    "output_tokens": None,
                }
            )
        ]
    )

    src = tmp_path / "doc.txt"
    src.write_text("Some Company invoice.\nSpecial marker: KRYPTONITE_MARKER_XYZ\nTotal: 10 EUR")
    pipeline.process(src, source="upload")

    rows = list_documents(q="KRYPTONITE_MARKER_XYZ")

    assert len(rows) == 1
    assert rows[0]["correspondent"] == "Some Company"
    assert "match_snippet" in rows[0]
    assert "KRYPTONITE_MARKER_XYZ" in rows[0]["match_snippet"]


def test_search_no_match_returns_empty(tmp_path, fake_chain):
    fake_chain(
        [
            FakeProvider(
                {
                    "correspondent": "Other Company",
                    "doc_type": "invoice",
                    "doc_date": "2026-01-01",
                    "expiry_date": None,
                    "amount_raw": None,
                    "summary": "Summary",
                    "full_text": None,
                    "evidence": [],
                    "raw_response": "{}",
                    "cost_usd": None,
                    "input_tokens": None,
                    "output_tokens": None,
                }
            )
        ]
    )
    src = tmp_path / "doc2.txt"
    src.write_text("Nothing special here.")
    pipeline.process(src, source="upload")

    rows = list_documents(q="doesnotexistanywhere")
    assert rows == []
