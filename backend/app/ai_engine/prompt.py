EXTRACTION_PROMPT_TEMPLATE = """Precitaj dokument na ceste {file_path} (faktura alebo zmluva, moze byt PDF/obrazok/text).
Vrat VYLUCNE jeden JSON objekt (ziadny iny text, ziadne markdown fence) s polami:
correspondent (nazov firmy/protistrany, kratky, bez diakritiky, vhodny do nazvu priecinka),
doc_type ("faktura" alebo "zmluva" alebo "ine"),
date (datum dokumentu vo formate YYYY-MM-DD, alebo null ak sa neda zistit),
amount (suma s menou ako text, napr. "123.45 EUR", alebo null ak nejde o fakturu),
summary (1-2 vety po slovensky, o com dokument je)."""


def build_prompt(file_path: str) -> str:
    return EXTRACTION_PROMPT_TEMPLATE.format(file_path=file_path)
