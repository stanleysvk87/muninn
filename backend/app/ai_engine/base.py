from pathlib import Path
from typing import Protocol, TypedDict


class ExtractionResult(TypedDict):
    correspondent: str
    doc_type: str
    doc_date: str | None
    amount_raw: str | None
    summary: str
    raw_response: str


class ExtractionError(Exception):
    pass


class AIProvider(Protocol):
    name: str
    model: str

    def extract(self, file_path: Path) -> ExtractionResult:
        ...
