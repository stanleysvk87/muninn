from pathlib import Path
from typing import Protocol, TypedDict


class ExtractionResult(TypedDict):
    correspondent: str
    doc_type: str
    doc_date: str | None
    expiry_date: str | None
    amount_raw: str | None
    summary: str
    summary_sk: str | None
    summary_en: str | None
    full_text: str | None
    evidence: list[dict] | None
    raw_response: str
    cost_usd: float | None
    input_tokens: int | None
    output_tokens: int | None


class ExtractionError(Exception):
    pass


class ProviderUnavailableError(ExtractionError):
    """Raised when a provider could not even attempt extraction -- auth
    failure, rate limit, timeout, missing binary/runtime -- as opposed to a
    content-level failure (bad JSON, garbled response, unreadable document)
    where retrying the same document later won't help. The ingest pipeline
    uses this distinction to decide whether a document should be queued for
    automatic retry once a provider comes back, instead of marked failed."""
    pass


class AIProvider(Protocol):
    name: str
    model: str

    def extract(self, file_path: Path) -> ExtractionResult:
        ...
