import json
import re
import subprocess
import tempfile
from pathlib import Path

from .base import ExtractionError, ExtractionResult
from .prompt import build_prompt

JSON_SPAN_RE = re.compile(r"\{.*\}", re.DOTALL)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class CodexCLIProvider:
    name = "codex_cli"
    model = "default"

    def extract(self, file_path: Path) -> ExtractionResult:
        prompt = build_prompt(file_path.name)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as out_f:
            output_path = Path(out_f.name)

        # POZOR: prompt musi byt HNED za "exec", pred -i/--image -- je to
        # variadicky flag (num_args = 1..) rovnako ako claude -p --add-dir/
        # --allowedTools, a zozerie nasledujuci argument ako dalsiu prilohu
        # namiesto promptu, co necha PROMPT prazdny a codex skonci s "No
        # prompt provided via stdin".
        cmd = [
            "codex",
            "exec",
            prompt,
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
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise ExtractionError(f"codex exec zlyhalo: {exc}") from exc
        finally:
            pass

        if proc.returncode != 0:
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
            amount_raw=data.get("amount"),
            summary=data.get("summary") or "",
            raw_response=result_text,
            # codex exec -o only writes the final text, not a cost/usage JSON
            # wrapper like `claude -p --output-format json` -- unknown for now.
            cost_usd=None,
            input_tokens=None,
            output_tokens=None,
        )
