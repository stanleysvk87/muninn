EXTRACTION_PROMPT_TEMPLATE = """Precitaj dokument na ceste {file_path}. Moze to byt faktura, zmluva,
rodny list, poistka, doklad totoznosti, alebo akykolvek iny dolezity osobny/rodinny dokument,
ktory by clovek chcel neskor rychlo najst. Moze byt PDF, obrazok alebo text.
Vrat VYLUCNE jeden JSON objekt (ziadny iny text, ziadne markdown fence) s polami:
correspondent (hlavny identifikator, podla ktoreho by clovek dokument hladal - nazov firmy/
protistrany pri fakture/zmluve/poistke, meno osoby pri rodnom liste/doklade totoznosti; kratky,
bez diakritiky, vhodny do nazvu priecinka),
doc_type (kratky slovensky nazov typu dokumentu, napr. "faktura", "zmluva", "rodny list",
"poistka", "doklad", "ine" - podla toho, co dokument skutocne je),
date (datum dokumentu vo formate YYYY-MM-DD, alebo null ak sa neda zistit),
amount (suma s menou ako text, napr. "123.45 EUR", alebo null ak sa dokumentu netyka ziadna suma),
summary (1-2 vety po slovensky, o com dokument je)."""


def build_prompt(file_path: str) -> str:
    return EXTRACTION_PROMPT_TEMPLATE.format(file_path=file_path)
