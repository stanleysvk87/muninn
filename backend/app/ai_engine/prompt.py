from pathlib import Path


MAX_INLINE_TEXT_CHARS = 18_000
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm"}


EXTRACTION_PROMPT_TEMPLATE = """Precitaj dokument na ceste {file_path}. Moze to byt faktura, zmluva,
rodny list, poistka, doklad totoznosti, alebo akykolvek iny dolezity osobny/rodinny dokument,
ktory by clovek chcel neskor rychlo najst. Moze byt PDF, obrazok alebo text.
Ak je obsah dokumentu vlozeny priamo v prompte nizsie, pouzi primarne tento vlozeny obsah.
Ak je prilozeny obrazok, citaj prilozeny obrazok.
Vrat VYLUCNE jeden JSON objekt (ziadny iny text, ziadne markdown fence) s polami:
correspondent (hlavny identifikator, podla ktoreho by clovek dokument hladal - nazov firmy/
protistrany pri fakture/zmluve/poistke, meno osoby pri rodnom liste/doklade totoznosti; kratky,
bez diakritiky, vhodny do nazvu priecinka),
doc_type (kratky slovensky nazov typu dokumentu, napr. "faktura", "zmluva", "rodny list",
"poistka", "doklad", "ine" - podla toho, co dokument skutocne je),
date (datum dokumentu vo formate YYYY-MM-DD, alebo null ak sa neda zistit),
amount (suma s menou ako text, napr. "123.45 EUR", alebo null ak sa dokumentu netyka ziadna suma),
expiry_date (datum platnosti/expiracie/obnovy vo formate YYYY-MM-DD - napr. kedy konci poistka,
kedy vyprsa zmluva alebo doklad totoznosti/vodicsky preukaz - alebo null ak sa dokumentu netyka
ziadny takyto datum),
summary (1-2 vety po slovensky, o com dokument je),
evidence (pole 0-5 objektov s poliami field, value, snippet, confidence; snippet je kratky citat/parafraza
casti dokumentu, confidence je cislo 0-1; ak si nie si isty alebo evidence nevies uviest, vrat prazdne pole)."""


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
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(file_path=file_path)
    if not document_text:
        return prompt
    return f"{prompt}\n\n--- ZACIATOK OBSAHU DOKUMENTU ---\n{document_text}\n--- KONIEC OBSAHU DOKUMENTU ---"
