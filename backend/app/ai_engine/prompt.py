from pathlib import Path


MAX_INLINE_TEXT_CHARS = 18_000
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm"}


EXTRACTION_PROMPT_TEMPLATE = """Read the document at path {file_path}. It can be an invoice,
contract, birth certificate, insurance policy, identity document, payslip, bank document,
medical document, school document, warranty, subscription notice, or any other important
personal/family document that should be easy to find later. It can be a PDF, image, Office
document or text.

If the document content is embedded directly in the prompt below, use that embedded content
as the primary source. If an image is attached, read the attached image.

Return EXACTLY one JSON object (no other text, no markdown fence) with these fields:
correspondent: main identifier a person would search for. Use a company/counterparty name
for invoices/contracts/insurance, or a person's name for birth certificates/identity
documents. Keep it short, ASCII without diacritics, suitable for a folder name.
doc_type: one stable lowercase key from this list only:
invoice, contract, birth_certificate, insurance_policy, identity_document, driver_license,
bank_statement, payslip, tax_document, medical_document, school_document, warranty,
subscription, receipt, correspondence, other.
date: document date in YYYY-MM-DD, or null if it cannot be determined.
amount: amount with currency as text, e.g. "123.45 EUR", or null if no amount applies.
expiry_date: validity/expiration/renewal date in YYYY-MM-DD, e.g. when insurance, a
contract, ID card, driver license, warranty or subscription expires; otherwise null.
summary_sk: 1-2 natural Slovak sentences describing what the document is about.
summary_en: 1-2 natural English sentences describing what the document is about.
summary: same value as summary_sk, kept for backward compatibility.
full_text: {full_text_instruction}.
evidence: array of 0-5 objects with field, value, snippet, confidence. Snippet may quote
or paraphrase the source document briefly. Confidence is a number from 0 to 1. If unsure
or evidence is not available, return an empty array."""

FULL_TEXT_INSTRUCTION_INLINE = (
    "obsah dokumentu je uz vlozeny vyssie v tomto prompte, takze ho tu NEOPAKUJ - vrat null"
)
FULL_TEXT_INSTRUCTION_TRANSCRIBE = (
    "cely citatelny text dokumentu (presna transkripcia vsetkeho textu na obrazku/v dokumente, "
    "pouzije sa len na fulltextove vyhladavanie) - ak dokument neobsahuje ziadny citatelny text, vrat null"
)


def read_inline_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    text = text.replace("\x00", "")
    if not text:
        return None
    if len(text) > MAX_INLINE_TEXT_CHARS:
        return text[:MAX_INLINE_TEXT_CHARS] + "\n\n[obsah skrateny]"
    return text


def build_prompt(file_path: str, document_text: str | None = None) -> str:
    full_text_instruction = (
        FULL_TEXT_INSTRUCTION_INLINE if document_text else FULL_TEXT_INSTRUCTION_TRANSCRIBE
    )
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        file_path=file_path, full_text_instruction=full_text_instruction
    )
    if not document_text:
        return prompt
    return f"{prompt}\n\n--- ZACIATOK OBSAHU DOKUMENTU ---\n{document_text}\n--- KONIEC OBSAHU DOKUMENTU ---"
