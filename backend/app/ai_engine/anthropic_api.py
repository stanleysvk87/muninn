import base64
import json
import mimetypes
from pathlib import Path

import anthropic

from .base import ExtractionError, ExtractionResult
from .prompt import build_prompt

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "correspondent": {"type": "string"},
        "doc_type": {"type": "string"},
        "date": {"type": ["string", "null"]},
        "amount": {"type": ["string", "null"]},
        "summary": {"type": "string"},
    },
    "required": ["correspondent", "doc_type", "date", "amount", "summary"],
    "additionalProperties": False,
}


class AnthropicAPIProvider:
    name = "anthropic_api"
    model = "claude-sonnet-5"

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def extract(self, file_path: Path) -> ExtractionResult:
        mime_type, _ = mimetypes.guess_type(file_path.name)
        data = base64.standard_b64encode(file_path.read_bytes()).decode()

        if mime_type == "application/pdf":
            content_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data},
            }
        elif mime_type and mime_type.startswith("image/"):
            content_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": data},
            }
        else:
            raise ExtractionError(f"nepodporovany typ suboru pre API fallback: {mime_type}")

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            content_block,
                            {"type": "text", "text": build_prompt(file_path.name)},
                        ],
                    }
                ],
            )
        except anthropic.APIStatusError as exc:
            raise ExtractionError(f"Anthropic API zlyhalo: {exc}") from exc

        if response.stop_reason == "refusal":
            raise ExtractionError("Model odmietol spracovat dokument")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise ExtractionError("Prazdna odpoved od API")

        data_json = json.loads(text)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        # Sonnet 5 standard rate ($3/$15 per MTok) -- an estimate, not the
        # billed-exact figure (doesn't account for prompt-cache discounts or
        # any temporary introductory pricing).
        cost_usd = (input_tokens * 3 + output_tokens * 15) / 1_000_000

        return ExtractionResult(
            correspondent=data_json.get("correspondent") or "neznama-firma",
            doc_type=data_json.get("doc_type") or "other",
            doc_date=data_json.get("date"),
            amount_raw=data_json.get("amount"),
            summary=data_json.get("summary") or "",
            raw_response=text,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
