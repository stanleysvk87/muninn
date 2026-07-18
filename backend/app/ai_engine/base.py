from pathlib import Path
from typing import Protocol, TypedDict


class ExtractionResult(TypedDict):
    correspondent: str
    doc_type: str
    doc_date: str | None
    expiry_date: str | None
    amount_raw: str | None
    summary: str
    full_text: str | None
    evidence: list[dict] | None
    raw_response: str
    cost_usd: float | None
    input_tokens: int | None
    output_tokens: int | None


class ExtractionError(Exception):
    pass


class AIProvider(Protocol):
    name: str
    model: str

    def extract(self, file_path: Path) -> ExtractionResult:
        ...
