import json
import re
import subprocess
from pathlib import Path

from .base import ExtractionError, ExtractionResult
from .prompt import build_prompt

JSON_SPAN_RE = re.compile(r"\{.*\}", re.DOTALL)


class ClaudeCLIProvider:
    name = "claude_cli"
    model = "default"  # whatever the CLI's own default/subscription model is

    def extract(self, file_path: Path) -> ExtractionResult:
        prompt = build_prompt(str(file_path))
        # POZOR: prompt musi byt HNED za -p. --add-dir a --allowedTools su
        # variadicke flagy (commander "...") a zozeru nasledujuci argument
        # ako svoju vlastnu hodnotu -- ak by prompt prisiel az za nimi,
        # claude -p skonci chybou "no prompt provided". Overene v
        # ~/scripts/dokumenty/process-dokument.sh.
        try:
            proc = subprocess.run(
                [
                    "claude",
                    "-p",
                    prompt,
                    "--output-format",
                    "json",
                    "--permission-mode",
                    "bypassPermissions",
                    "--allowedTools",
                    "Read",
                    "--add-dir",
                    str(file_path.parent),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise ExtractionError(f"claude -p zlyhalo: {exc}") from exc

        if proc.returncode != 0:
            raise ExtractionError(f"claude -p vratilo chybu: {proc.stderr[:500]}")

        try:
            outer = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"claude -p vratilo neplatny JSON obal: {exc}") from exc

        result_text = outer.get("result") or ""
        match = JSON_SPAN_RE.search(result_text)
        if not match:
            raise ExtractionError(f"odpoved modelu neobsahuje JSON: {result_text[:500]}")

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"nepodarilo sa naparsovat JSON od modelu: {exc}") from exc

        usage = outer.get("usage") or {}
        input_tokens = (
            (usage.get("input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0)
        ) or None

        return ExtractionResult(
            correspondent=data.get("correspondent") or "neznama-firma",
            doc_type=data.get("doc_type") or "other",
            doc_date=data.get("date"),
            amount_raw=data.get("amount"),
            summary=data.get("summary") or "",
            raw_response=result_text,
            cost_usd=outer.get("total_cost_usd"),
            input_tokens=input_tokens,
            output_tokens=usage.get("output_tokens"),
        )
