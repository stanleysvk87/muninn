import json
import re
import subprocess
import tempfile
from pathlib import Path

from .base import ExtractionError, ExtractionResult, ProviderUnavailableError
from .prompt import build_prompt, read_inline_text

JSON_SPAN_RE = re.compile(r"\{.*\}", re.DOTALL)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
# codex exec has no structured error envelope like claude -p does -- these
# are stderr substrings seen for "the provider itself isn't usable right
# now" failures (auth/quota/missing runtime), as opposed to a content
# problem. Not exhaustive, just the ones observed in practice.
UNAVAILABLE_STDERR_SIGNALS = (
    "authentication",
    "unauthorized",
    "401",
    "403",
    "429",
    "rate limit",
    "quota",
    "no such file or directory",  # e.g. missing `node` runtime for codex.js
)


def _is_unavailable(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(signal in lowered for signal in UNAVAILABLE_STDERR_SIGNALS)


class CodexCLIProvider:
    name = "codex_cli"
    model = "default"

    def extract(self, file_path: Path) -> ExtractionResult:
        prompt = build_prompt(file_path.name, read_inline_text(file_path))

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as out_f:
            output_path = Path(out_f.name)

        # Prompt ide cez stdin, nie ako argv element -- rovnake riziko ako
        # v claude_cli.py vyssie (dlhy OCR text z viacstranoveho PDF moze
        # presiahnut limit velkosti argv jadra). Vynechanie poziciovneho
        # PROMPT argumentu necha codex citat ho zo stdin -- a zaroven to
        # odstranuje aj povodne riziko, ze -i/--image (variadicky flag) by
        # prompt zozral ako dalsiu prilohu, lebo prompt uz medzi argv
        # vobec nie je.
        cmd = [
            "codex",
            "exec",
            "-C",
            str(file_path.parent),
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "-o",
            str(output_path),
        ]
        if file_path.suffix.lower() in IMAGE_SUFFIXES:
            cmd += ["-i", str(file_path)]

        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise ProviderUnavailableError(f"codex exec zlyhalo: {exc}") from exc
        finally:
            pass

        if proc.returncode != 0:
            if _is_unavailable(proc.stderr or ""):
                raise ProviderUnavailableError(f"codex exec vratilo chybu: {proc.stderr[:500]}")
            raise ExtractionError(f"codex exec vratilo chybu: {proc.stderr[:500]}")

        try:
            result_text = output_path.read_text()
        finally:
            output_path.unlink(missing_ok=True)

        match = JSON_SPAN_RE.search(result_text)
        if not match:
            raise ExtractionError(f"odpoved modelu neobsahuje JSON: {result_text[:500]}")

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"nepodarilo sa naparsovat JSON od modelu: {exc}") from exc

        return ExtractionResult(
            correspondent=data.get("correspondent") or "neznama-firma",
            doc_type=data.get("doc_type") or "other",
            doc_date=data.get("date"),
            expiry_date=data.get("expiry_date"),
            amount_raw=data.get("amount"),
            summary=data.get("summary") or data.get("summary_sk") or "",
            summary_sk=data.get("summary_sk") or data.get("summary"),
            summary_en=data.get("summary_en"),
            full_text=data.get("full_text") or None,
            evidence=data.get("evidence") if isinstance(data.get("evidence"), list) else None,
            raw_response=result_text,
            # codex exec -o only writes the final text, not a cost/usage JSON
            # wrapper like `claude -p --output-format json` -- unknown for now.
            cost_usd=None,
            input_tokens=None,
            output_tokens=None,
        )
