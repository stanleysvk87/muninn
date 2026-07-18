"""Structured API errors.

HTTPException.detail used to be a hardcoded Slovak sentence, so an
English-UI user hit Slovak text on every 4xx/5xx response regardless of
their language choice. Every error site here instead raises with a
stable `code`; the frontend looks the code up in its own SK/EN
dictionary (frontend/src/i18n.jsx) and falls back to the `message`
below (always Slovak) only for codes it doesn't recognize.
"""
from fastapi import HTTPException

_MESSAGES: dict[str, str] = {
    "invalid_filename": "Chýba názov súboru",
    "merge_needs_two_files": "Zlúčenie potrebuje aspoň 2 súbory",
    "merge_unsupported_format": "Zlúčenie podporuje len obrázky a PDF, nie {suffix}",
    "merge_failed": "Zlúčenie súborov zlyhalo: {error}",
    "admin_already_exists": "Admin účet už existuje",
    "username_password_required": "Používateľské meno a heslo (min. 8 znakov) sú povinné",
    "consent_required": "Musíš súhlasiť so spracovaním dokumentov (vrátane odosielania obsahu AI poskytovateľom)",
    "invalid_credentials": "Nesprávne meno alebo heslo",
    "not_authenticated": "Neprihlásený",
    "folder_invalid": "Priečinok neexistuje alebo cesta chýba",
    "stored_path_not_a_file": "Uložená cesta nie je súbor; odmietam ju zmazať automaticky",
    "file_delete_failed": "Nepodarilo sa zmazať súbor z disku: {error}",
    "saved_view_not_found": "Saved view nenájdený",
    "saved_view_invalid_config": "Saved view má neplatnú konfiguráciu",
    "invalid_id_list": "Neplatný zoznam id",
    "unknown_export_format": "Neznámy formát (použi json, csv alebo zip)",
    "document_not_found": "Dokument nenájdený",
    "invalid_duplicate_status": "Neplatný duplicate status",
    "duplicate_warning_not_found": "Duplikátový warning nenájdený",
    "file_not_found_on_disk": "Súbor sa na disku nenašiel (možno zlyhalo spracovanie)",
    "invalid_review_status": "Neplatný review status",
    "retry_not_allowed": "Retry je dostupný len pre failed alebo pending dokumenty",
    "original_file_not_found": "Pôvodný súbor sa na disku nenašiel",
    "no_ids_to_delete": "Žiadne id na zmazanie",
}


def api_error(status_code: int, code: str, **params: object) -> HTTPException:
    template = _MESSAGES[code]
    message = template.format(**params) if params else template
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, "params": params})
