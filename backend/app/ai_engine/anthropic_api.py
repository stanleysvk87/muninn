import base64
import json
import mimetypes
from pathlib import Path

import anthropic

from .base import ExtractionError, ExtractionResult, ProviderUnavailableError
from .prompt import build_prompt, read_inline_text

UNAVAILABLE_STATUS_CODES = {401, 403, 429, 500, 502, 503, 529}

# The prompt asks for a full transcription (full_text) of the document on top
# of the metadata, and on Sonnet 5 adaptive thinking is on by default and is
# counted against this same limit. 1024 was nowhere near enough: a two-page
# contract came back truncated, the JSON was incomplete, and json.loads()
# raised JSONDecodeError -- which is NOT an ExtractionError, so it escaped the
# whole ingest pipeline as an unhandled 500 (no document row, no park_failed,
# leaked temp dir).
MAX_TOKENS = 8192

# Sonnet 5 introductory pricing, USD per million tokens, valid until
# 2026-08-31; the standard rate afterwards is $3 / $15. Estimate only -- it
# ignores prompt-cache discounts. Kept as named constants so the switch-over
# is a one-line edit instead of a magic number in an expression.
INPUT_USD_PER_MTOK = 2.0
OUTPUT_USD_PER_MTOK = 10.0

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "correspondent": {"type": "string"},
        "doc_type": {
            "type": "string",
            "enum": [
                "invoice", "contract", "birth_certificate", "insurance_policy",
                "identity_document", "driver_license", "bank_statement", "payslip",
                "tax_document", "medical_document", "school_document", "warranty",
                "subscription", "receipt", "correspondence", "other",
            ],
        },
        "date": {"type": ["string", "null"]},
        "expiry_date": {"type": ["string", "null"]},
        "amount": {"type": ["string", "null"]},
        "summary": {"type": "string"},
        "summary_sk": {"type": "string"},
        "summary_en": {"type": "string"},
        "full_text": {"type": ["string", "null"]},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": ["string", "null"]},
                    "snippet": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["field", "value", "snippet", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "correspondent", "doc_type", "date", "expiry_date", "amount",
        "summary", "summary_sk", "summary_en", "full_text", "evidence",
    ],
    "additionalProperties": False,
}


class AnthropicAPIProvider:
    name = "anthropic_api"
    model = "claude-sonnet-5"

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def extract(self, file_path: Path) -> ExtractionResult:
        mime_type, _ = mimetypes.guess_type(file_path.name)
        inline_text = read_inline_text(file_path)

        if inline_text:
            content = [{"type": "text", "text": build_prompt(file_path.name, inline_text)}]
        else:
            data = base64.standard_b64encode(file_path.read_bytes()).decode()
            content_block = None
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
            content_block = {
                **content_block,
            }
            content = [content_block, {"type": "text", "text": build_prompt(file_path.name)}]

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
            )
        except anthropic.APIConnectionError as exc:
            # No HTTP status at all -- network/DNS/timeout, clearly an
            # availability problem rather than anything to do with this document.
            raise ProviderUnavailableError(f"Anthropic API nedostupne: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code in UNAVAILABLE_STATUS_CODES:
                raise ProviderUnavailableError(f"Anthropic API zlyhalo ({exc.status_code}): {exc}") from exc
            raise ExtractionError(f"Anthropic API zlyhalo: {exc}") from exc

        if response.stop_reason == "refusal":
            raise ExtractionError("Model odmietol spracovat dokument")
        if response.stop_reason == "max_tokens":
            # Truncated output means the JSON below is incomplete. Fail as an
            # ExtractionError so the pipeline can park the file and fall
            # through to the next provider, instead of blowing up on a
            # JSONDecodeError nobody catches.
            raise ExtractionError(
                f"Odpoved modelu bola orezana na limite {MAX_TOKENS} tokenov "
                "(prilis dlhy dokument) - JSON je neuplny"
            )

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise ExtractionError("Prazdna odpoved od API")

        try:
            data_json = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"Neplatny JSON od Anthropic API: {exc}") from exc

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = (
            input_tokens * INPUT_USD_PER_MTOK + output_tokens * OUTPUT_USD_PER_MTOK
        ) / 1_000_000

        return ExtractionResult(
            correspondent=data_json.get("correspondent") or "neznama-firma",
            doc_type=data_json.get("doc_type") or "other",
            doc_date=data_json.get("date"),
            expiry_date=data_json.get("expiry_date"),
            amount_raw=data_json.get("amount"),
            summary=data_json.get("summary") or data_json.get("summary_sk") or "",
            summary_sk=data_json.get("summary_sk") or data_json.get("summary"),
            summary_en=data_json.get("summary_en"),
            full_text=data_json.get("full_text") or None,
            evidence=data_json.get("evidence") if isinstance(data_json.get("evidence"), list) else None,
            raw_response=text,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
