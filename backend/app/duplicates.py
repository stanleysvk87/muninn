from difflib import SequenceMatcher
from datetime import date
from unicodedata import combining, normalize

from .audit import add_document_event
from .db import execute


def _clean(value: str | None) -> str:
    if not value:
        return ""
    text = normalize("NFKD", value)
    text = "".join(ch for ch in text if not combining(ch))
    return "".join(ch.lower() for ch in text if ch.isalnum() or ch.isspace()).strip()


def _similarity(left: str | None, right: str | None) -> float:
    a = _clean(left)
    b = _clean(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _days_apart(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    try:
        return abs((date.fromisoformat(left) - date.fromisoformat(right)).days)
    except ValueError:
        return None


def find_duplicate_candidates(document_id: int) -> list[dict]:
    doc = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc is None or doc["status"] != "processed":
        return []

    rows = execute(
        """SELECT * FROM documents
           WHERE id != ? AND status = 'processed'
           ORDER BY created_at DESC
           LIMIT 300""",
        (document_id,),
    ).fetchall()
    candidates = []

    for other in rows:
        reasons = []
        score = 0.0
        corr_score = _similarity(doc["correspondent"], other["correspondent"])
        type_score = _similarity(doc["doc_type"], other["doc_type"])
        date_gap = _days_apart(doc["doc_date"], other["doc_date"])
        expiry_gap = _days_apart(doc["expiry_date"], other["expiry_date"])

        if doc["file_hash"] and doc["file_hash"] == other["file_hash"]:
            score += 1.0
            reasons.append("rovnaky hash suboru")
        if corr_score >= 0.82:
            score += 0.35 * corr_score
            reasons.append("podobna firma/osoba")
        if type_score >= 0.8:
            score += 0.12 * type_score
            reasons.append("podobny typ")
        if doc["amount_value"] is not None and other["amount_value"] is not None:
            amount_delta = abs(float(doc["amount_value"]) - float(other["amount_value"]))
            allowed_delta = max(0.01, abs(float(doc["amount_value"])) * 0.005)
            if amount_delta <= allowed_delta:
                score += 0.28
                reasons.append("rovnaka alebo velmi podobna suma")
        if date_gap is not None and date_gap <= 7:
            score += 0.15
            reasons.append("blizky datum dokumentu")
        if expiry_gap is not None and expiry_gap <= 7:
            score += 0.1
            reasons.append("blizka expiracia")

        if score >= 0.55 and reasons:
            candidates.append(
                {
                    "candidate_id": other["id"],
                    "score": min(score, 1.0),
                    "reason": ", ".join(reasons),
                }
            )

    return sorted(candidates, key=lambda item: item["score"], reverse=True)[:5]


def record_duplicate_candidates(document_id: int) -> list[dict]:
    candidates = find_duplicate_candidates(document_id)
    for candidate in candidates:
        execute(
            """INSERT OR IGNORE INTO document_duplicate_candidates
                 (document_id, candidate_id, score, reason, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', datetime('now'), datetime('now'))""",
            (
                document_id,
                candidate["candidate_id"],
                candidate["score"],
                candidate["reason"],
            ),
        )
    if candidates:
        add_document_event(
            document_id,
            "duplicate_warning",
            f"Najdene mozne duplikaty: {len(candidates)}",
            metadata={"candidates": candidates},
        )
    return candidates
