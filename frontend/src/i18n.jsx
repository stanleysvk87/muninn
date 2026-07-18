import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "muninn-language";
const SUPPORTED_LANGUAGES = ["sk", "en"];

const DICTIONARIES = {
  sk: {
    "common.loading": "Načítavam...",
    "common.error": "Chyba",
    "common.ok": "OK",
    "common.none": "Žiadne",
    "common.unknown": "neznámy",
    "common.providerUnknown": "provider?",
    "common.noDetail": "bez detailu",
    "common.download": "Stiahnuť",
    "common.save": "Uložiť",
    "common.cancel": "Zrušiť",
    "common.remove": "Odstrániť",
    "common.delete": "Zmazať",
    "common.edit": "Upraviť",
    "common.view": "Zobraziť",
    "common.search": "Hľadať",
    "common.retry": "Skúsiť znova",
    "common.language": "Jazyk",
    "common.slovak": "Slovenčina",
    "common.english": "English",

    "nav.dashboard": "Prehľad",
    "nav.search": "Hľadanie",
    "nav.upload": "Nahrať",
    "nav.settings": "Nastavenia",
    "nav.logout": "Odhlásiť",
    "nav.openMenu": "Otvoriť menu",
    "nav.closeMenu": "Zavrieť menu",
    "nav.home": "Muninn domov",
    "nav.expand": "Rozbaliť menu",
    "nav.collapse": "Zbaliť menu",

    "status.processed": "Spracované",
    "status.failed": "Zlyhalo",
    "status.pending": "Čaká",
    "status.processing": "Spracováva sa",

    "review.na_kontrolu": "Na kontrolu",
    "review.zaplatit": "Zaplatiť",
    "review.vybavene": "Vybavené",
    "review.zamietnute": "Zamietnuté",
    "review.archiv": "Archív",

    "recurrence.monthly": "Mesačne",
    "recurrence.quarterly": "Štvrťročne",
    "recurrence.yearly": "Ročne",

    "dashboard.eyebrow": "Muninn",
    "dashboard.title": "Prehľad",
    "dashboard.description": "Rýchly pohľad na archív a hlavné akcie.",
    "dashboard.uploadDocument": "Nahrať dokument",
    "dashboard.documents": "Dokumentov",
    "dashboard.correspondents": "Firiem / osôb",
    "dashboard.failedProcessing": "Zlyhalo spracovanie",
    "dashboard.pendingProcessing": "Vo fronte na spracovanie",
    "dashboard.expiringSoon": "Blíži sa expirácia",
    "dashboard.validUntil": "{type} · platí do {date}",
    "dashboard.overdue": "po termíne {count} {unit}",
    "dashboard.inDays": "o {count} {unit}",
    "dashboard.done": "Vybavené",
    "dashboard.workViews": "Pracovné pohľady",
    "dashboard.loadingViews": "Načítavam pohľady...",
    "dashboard.recent": "Naposledy pridané",
    "dashboard.empty": "Zatiaľ tu nič nie je.",
    "dashboard.uploadFirst": "Nahraj prvý dokument",

    "savedView.review.label": "Na kontrolu",
    "savedView.review.description": "Dokumenty, ktoré treba ešte skontrolovať alebo rozhodnúť.",
    "savedView.pay.label": "Zaplatiť",
    "savedView.pay.description": "Faktúry alebo platby označené na vybavenie.",
    "savedView.expiring.label": "Expirácie",
    "savedView.expiring.description": "Aktívne dokumenty s dátumom expirácie alebo obnovy.",
    "savedView.failed.label": "Zlyhania",
    "savedView.failed.description": "Súbory, ktoré neprešli spracovaním.",
    "savedView.pending.label": "Vo fronte",
    "savedView.pending.description": "AI momentálne nedostupné - spracujú sa automaticky, keď provider nabehne.",
    "savedView.duplicates.label": "Možné duplikáty",
    "savedView.duplicates.description": "Dokumenty s otvoreným upozornením na duplicitu.",

    "upload.eyebrow": "Príjem dokumentov",
    "upload.title": "Nahrať dokument",
    "upload.description": "Presuň sem PDF alebo fotky, prípadne ich odfoť priamo mobilom. Máš viac strán tej istej zmluvy? Pridaj ich všetky a zlúč ich do jedného dokumentu.",
    "upload.drop": "Presuň sem súbory alebo",
    "upload.chooseFiles": "Vybrať súbory",
    "upload.takePhoto": "Odfoť mobilom",
    "upload.ready": "Pripravené na nahratie ({count})",
    "upload.up": "Hore",
    "upload.down": "Dole",
    "upload.upload": "Nahrať",
    "upload.combine": "Zlúčiť do jedného dokumentu ({count} {unit})",
    "upload.eachSeparately": "Nahrať každý zvlášť",
    "upload.processing": "Spracovávam...",
    "upload.duplicate": "Tento dokument už máš archivovaný (dokument #{id}); nespracoval sa znova.",
    "upload.combined": "Zlúčených {count} {unit} do jedného dokumentu a spracované (dokument #{id}).",
    "upload.processed": "Nahrané a spracované (dokument #{id}).",
    "upload.uploadedSeparate": "Nahrané samostatne: {count} {unit}.",
    "upload.failed": "Nahratie zlyhalo",
    "upload.combineFailed": "Zlúčenie zlyhalo",
    "upload.failedAfter": "Nahratie zlyhalo po {count} {unit}.",

    "search.eyebrow": "Archív",
    "search.title": "Hľadanie",
    "search.expirations": "Expirácie",
    "search.view": "Pohľad",
    "search.expiringDescription": "Aktívne upozornenia, ktoré ešte nie sú označené ako vybavené.",
    "search.savedViewDescription": "Uložený pracovný pohľad z dashboardu.",
    "search.description": "Zadaj meno firmy alebo časť textu, napríklad „uniqa“.",
    "search.allDocuments": "Všetky dokumenty",
    "search.placeholder": "Hľadať...",
    "search.filters": "Filtre",
    "search.clearFilters": "Zrušiť filtre",
    "search.selected": "{count} označených",
    "search.downloadZip": "Stiahnuť ako ZIP",
    "search.deleteSelected": "Zmazať označené",
    "search.deleteConfirm": "Naozaj zmazať {count} vybraných dokumentov?",
    "search.loadFailed": "Nepodarilo sa načítať dokumenty",
    "search.empty": "Žiadne dokumenty",
    "search.selectDocument": "Označiť dokument {name}",
    "search.validUntil": "platí do {date}",

    "table.correspondent": "Firma / osoba",
    "table.type": "Typ",
    "table.date": "Dátum",
    "table.validUntil": "Platí do",
    "table.amount": "Suma",
    "table.status": "Stav",
    "table.summary": "Zhrnutie",

    "login.title": "Prihlásenie",
    "login.bootstrapTitle": "Vytvorenie admin účtu",
    "login.username": "Používateľské meno",
    "login.password": "Heslo",
    "login.failed": "Prihlásenie zlyhalo",
    "login.submit": "Prihlásiť sa",
    "login.createAccount": "Vytvoriť účet",
    "login.firstRun": "Prvé spustenie? Vytvoriť admin účet",
    "login.haveAccount": "Už mám účet",
    "login.consentPrefix": "Súhlasím so spracovaním mojich dokumentov vrátane odosielania obsahu AI poskytovateľom (Claude/Codex/Anthropic) na extrakciu a beriem na vedomie zrieknutie sa zodpovednosti (softvér „tak ako je“, spracovanie treťou stranou mimo kontroly prevádzkovateľa). Viac v",
    "login.privacy": "Ochrane údajov",

    "detail.back": "Späť na hľadanie",
    "detail.notFound": "Dokument sa nenašiel",
    "detail.reviewStatus": "Review stav",
    "detail.type": "Typ",
    "detail.date": "Dátum",
    "detail.validUntil": "Platí do",
    "detail.alert": "Upozornenie",
    "detail.doneAt": "Vybavené {date}",
    "detail.recurrence": "Opakované upozornenie",
    "detail.next": "ďalšie {date}",
    "detail.amount": "Suma",
    "detail.summary": "Zhrnutie",
    "detail.source": "Zdroj",
    "detail.originalName": "Pôvodný názov",
    "detail.storedIn": "Uložené v",
    "detail.aiEvidence": "AI dôkazy",
    "detail.possibleDuplicates": "Možné duplikáty",
    "detail.confirmDuplicate": "Potvrdiť",
    "detail.ignoreDuplicate": "Ignorovať",
    "detail.hideAlert": "Skryť upozornenie",
    "detail.restoreAlert": "Obnoviť upozornenie",
    "detail.deleteConfirm": "Naozaj zmazať tento dokument?",
    "detail.company": "Firma",
    "detail.dateInput": "Dátum (YYYY-MM-DD)",
    "detail.validUntilInput": "Platí do (YYYY-MM-DD)",
    "detail.recurrenceInput": "Opakované upozornenie (napr. poistka, predplatné)",
    "detail.auditTimeline": "Audit timeline",
    "detail.noEvents": "Zatiaľ žiadne udalosti.",
    "event.history_backfill": "Dokument bol v databáze pred zapnutím audit timeline.",
    "event.duplicate_status": "Upozornenie na duplicitu bolo aktualizované.",
    "event.expiry_dismissed": "Expiračné upozornenie bolo označené ako vybavené.",
    "event.expiry_restored": "Expiračné upozornenie bolo obnovené.",
    "event.document_updated": "Metadáta dokumentu boli upravené.",
    "event.review_status": "Review stav zmenený na {status}.",
    "event.retry_started": "Spustený manuálny retry failed dokumentu.",
    "event.retry_finished": "Manuálny retry skončil stavom {status}.",
    "event.duplicate_warning": "Nájdené možné duplikáty: {count}.",
    "event.duplicate_exact": "Preskočený byte-identický duplicitný súbor.",
    "event.ingest_failed": "Spracovanie dokumentu zlyhalo.",
    "event.ingest_pending": "AI momentálne nedostupné - dokument čaká vo fronte na automatické spracovanie.",
    "event.ingested": "Dokument bol spracovaný.",

    "duplicateReason.rovnaky hash suboru": "rovnaký hash súboru",
    "duplicateReason.podobna firma/osoba": "podobná firma/osoba",
    "duplicateReason.podobny typ": "podobný typ",
    "duplicateReason.rovnaka alebo velmi podobna suma": "rovnaká alebo veľmi podobná suma",
    "duplicateReason.blizky datum dokumentu": "blízky dátum dokumentu",
    "duplicateReason.blizka expiracia": "blízka expirácia",

    "settings.eyebrow": "Konfigurácia",
    "settings.title": "Nastavenia",
    "settings.watchFolders": "Sledované priečinky",
    "settings.noFolders": "Žiadne priečinky",
    "settings.folderPlaceholder": "/cesta/k/priecinku",
    "settings.add": "Pridať",
    "settings.mail": "Mail (voliteľné)",
    "settings.enableMail": "Zapnúť mail ingestion",
    "settings.imapHost": "IMAP host",
    "settings.port": "Port",
    "settings.username": "Používateľské meno",
    "settings.password": "Heslo",
    "settings.telegram": "Telegram upozornenia",
    "settings.telegramDescription": "Keď sa blíži platnosť dokumentu (poistka, zmluva, doklad), pošlem správu na Telegram.",
    "settings.enableTelegram": "Zapnúť Telegram upozornenia",
    "settings.botToken": "Bot token (od @BotFather)",
    "settings.chatId": "Chat ID",
    "settings.notifyDays": "Koľko dní vopred upozorniť",
    "settings.tokenStored": "Bot token je uložený šifrovane. Nechaj pole prázdne, ak ho nechceš meniť.",
    "settings.test": "Otestovať",
    "settings.aiEngine": "AI engine",
    "settings.modeAuto": "Automaticky (Claude/Codex CLI, potom API kľúč)",
    "settings.modeClaude": "Len Claude CLI",
    "settings.modeCodex": "Len Codex CLI",
    "settings.modeAnthropic": "Len Anthropic API kľúč",
    "settings.apiKey": "Anthropic API kľúč (ak treba)",
    "settings.testConnection": "Otestovať pripojenie",
    "settings.aiUsage": "Spotreba AI",
    "settings.noProcessed": "Zatiaľ žiadne spracované dokumenty",
    "settings.processedDocuments": "Spracovaných dokumentov",
    "settings.tokenCosts": "API/Claude token náklady",
    "settings.measuredTokens": "Merané tokeny in/out",
    "settings.cliCalls": "CLI volania",
    "settings.provider": "Provider",
    "settings.documents": "Dokumentov",
    "settings.costs": "Náklady",
    "settings.tokens": "Tokeny in/out",
    "settings.technicalStatus": "Technický stav",
    "settings.aiMode": "AI režim",
    "settings.available": "dostupný",
    "settings.missing": "chýba",
    "settings.mailUidFailed": "Mail UID / failed",
    "settings.providerChain": "Provider chain",
    "settings.recentErrors": "Posledné chyby",
    "settings.noFailed": "Žiadne failed dokumenty v aktívnej DB.",
    "settings.recentJobs": "Posledné joby",
    "settings.refreshStatus": "Obnoviť stav",
    "settings.privacyLink": "Ochrana údajov a AI spracovanie",
    "settings.testError": "Chyba: {detail}",
  },
  en: {
    "common.loading": "Loading...",
    "common.error": "Error",
    "common.ok": "OK",
    "common.none": "None",
    "common.unknown": "unknown",
    "common.providerUnknown": "provider?",
    "common.noDetail": "no detail",
    "common.download": "Download",
    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.remove": "Remove",
    "common.delete": "Delete",
    "common.edit": "Edit",
    "common.view": "Open",
    "common.search": "Search",
    "common.retry": "Retry",
    "common.language": "Language",
    "common.slovak": "Slovenčina",
    "common.english": "English",

    "nav.dashboard": "Overview",
    "nav.search": "Search",
    "nav.upload": "Upload",
    "nav.settings": "Settings",
    "nav.logout": "Sign out",
    "nav.openMenu": "Open menu",
    "nav.closeMenu": "Close menu",
    "nav.home": "Muninn home",
    "nav.expand": "Expand menu",
    "nav.collapse": "Collapse menu",

    "status.processed": "Processed",
    "status.failed": "Failed",
    "status.pending": "Queued",
    "status.processing": "Processing",

    "review.na_kontrolu": "Needs review",
    "review.zaplatit": "To pay",
    "review.vybavene": "Done",
    "review.zamietnute": "Rejected",
    "review.archiv": "Archive",

    "recurrence.monthly": "Monthly",
    "recurrence.quarterly": "Quarterly",
    "recurrence.yearly": "Yearly",

    "dashboard.eyebrow": "Muninn",
    "dashboard.title": "Overview",
    "dashboard.description": "A quick view of the archive and primary actions.",
    "dashboard.uploadDocument": "Upload document",
    "dashboard.documents": "Documents",
    "dashboard.correspondents": "Companies / people",
    "dashboard.failedProcessing": "Processing failed",
    "dashboard.pendingProcessing": "Queued for processing",
    "dashboard.expiringSoon": "Expiring soon",
    "dashboard.validUntil": "{type} · valid until {date}",
    "dashboard.overdue": "{count} {unit} overdue",
    "dashboard.inDays": "in {count} {unit}",
    "dashboard.done": "Done",
    "dashboard.workViews": "Work views",
    "dashboard.loadingViews": "Loading views...",
    "dashboard.recent": "Recently added",
    "dashboard.empty": "There is nothing here yet.",
    "dashboard.uploadFirst": "Upload the first document",

    "savedView.review.label": "Needs review",
    "savedView.review.description": "Documents that still need checking or a decision.",
    "savedView.pay.label": "To pay",
    "savedView.pay.description": "Invoices or payments marked for action.",
    "savedView.expiring.label": "Expirations",
    "savedView.expiring.description": "Active documents with an expiration or renewal date.",
    "savedView.failed.label": "Failures",
    "savedView.failed.description": "Files that did not process successfully.",
    "savedView.pending.label": "Queued",
    "savedView.pending.description": "AI is currently unavailable - these will process automatically once a provider is back.",
    "savedView.duplicates.label": "Possible duplicates",
    "savedView.duplicates.description": "Documents with an open duplicate warning.",

    "upload.eyebrow": "Document intake",
    "upload.title": "Upload document",
    "upload.description": "Drop PDFs or photos here, or take a photo directly on your phone. Multiple pages of the same contract? Add them all and merge them into one document.",
    "upload.drop": "Drop files here or",
    "upload.chooseFiles": "Choose files",
    "upload.takePhoto": "Take photo",
    "upload.ready": "Ready to upload ({count})",
    "upload.up": "Up",
    "upload.down": "Down",
    "upload.upload": "Upload",
    "upload.combine": "Merge into one document ({count} {unit})",
    "upload.eachSeparately": "Upload each separately",
    "upload.processing": "Processing...",
    "upload.duplicate": "This document is already archived (document #{id}); it was not processed again.",
    "upload.combined": "Merged {count} {unit} into one document and processed it (document #{id}).",
    "upload.processed": "Uploaded and processed (document #{id}).",
    "upload.uploadedSeparate": "Uploaded separately: {count} {unit}.",
    "upload.failed": "Upload failed",
    "upload.combineFailed": "Merge failed",
    "upload.failedAfter": "Upload failed after {count} {unit}.",

    "search.eyebrow": "Archive",
    "search.title": "Search",
    "search.expirations": "Expirations",
    "search.view": "View",
    "search.expiringDescription": "Active alerts that have not been marked as done yet.",
    "search.savedViewDescription": "Saved work view from the dashboard.",
    "search.description": "Enter a company name or part of the text, for example \"uniqa\".",
    "search.allDocuments": "All documents",
    "search.placeholder": "Search...",
    "search.filters": "Filters",
    "search.clearFilters": "Clear filters",
    "search.selected": "{count} selected",
    "search.downloadZip": "Download as ZIP",
    "search.deleteSelected": "Delete selected",
    "search.deleteConfirm": "Delete {count} selected documents?",
    "search.loadFailed": "Could not load documents",
    "search.empty": "No documents",
    "search.selectDocument": "Select document {name}",
    "search.validUntil": "valid until {date}",

    "table.correspondent": "Company / person",
    "table.type": "Type",
    "table.date": "Date",
    "table.validUntil": "Valid until",
    "table.amount": "Amount",
    "table.status": "Status",
    "table.summary": "Summary",

    "login.title": "Sign in",
    "login.bootstrapTitle": "Create admin account",
    "login.username": "Username",
    "login.password": "Password",
    "login.failed": "Sign-in failed",
    "login.submit": "Sign in",
    "login.createAccount": "Create account",
    "login.firstRun": "First run? Create admin account",
    "login.haveAccount": "I already have an account",
    "login.consentPrefix": "I agree to the processing of my documents, including sending their content to AI providers (Claude/Codex/Anthropic) for extraction, and I acknowledge the disclaimer (software provided \"as is\", third-party processing outside the operator's control). More in",
    "login.privacy": "Privacy notice",

    "detail.back": "Back to search",
    "detail.notFound": "Document was not found",
    "detail.reviewStatus": "Review status",
    "detail.type": "Type",
    "detail.date": "Date",
    "detail.validUntil": "Valid until",
    "detail.alert": "Alert",
    "detail.doneAt": "Done {date}",
    "detail.recurrence": "Recurring alert",
    "detail.next": "next {date}",
    "detail.amount": "Amount",
    "detail.summary": "Summary",
    "detail.source": "Source",
    "detail.originalName": "Original name",
    "detail.storedIn": "Stored in",
    "detail.aiEvidence": "AI evidence",
    "detail.possibleDuplicates": "Possible duplicates",
    "detail.confirmDuplicate": "Confirm",
    "detail.ignoreDuplicate": "Ignore",
    "detail.hideAlert": "Hide alert",
    "detail.restoreAlert": "Restore alert",
    "detail.deleteConfirm": "Delete this document?",
    "detail.company": "Company",
    "detail.dateInput": "Date (YYYY-MM-DD)",
    "detail.validUntilInput": "Valid until (YYYY-MM-DD)",
    "detail.recurrenceInput": "Recurring alert (for example insurance, subscription)",
    "detail.auditTimeline": "Audit timeline",
    "detail.noEvents": "No events yet.",
    "event.history_backfill": "The document was already in the database before the audit timeline was enabled.",
    "event.duplicate_status": "Duplicate warning was updated.",
    "event.expiry_dismissed": "Expiration alert was marked as done.",
    "event.expiry_restored": "Expiration alert was restored.",
    "event.document_updated": "Document metadata was updated.",
    "event.review_status": "Review status changed to {status}.",
    "event.retry_started": "Manual retry started for the failed document.",
    "event.retry_finished": "Manual retry finished with status {status}.",
    "event.duplicate_warning": "Possible duplicates found: {count}.",
    "event.duplicate_exact": "Skipped a byte-identical duplicate file.",
    "event.ingest_failed": "Document processing failed.",
    "event.ingest_pending": "AI is currently unavailable - the document is queued for automatic processing.",
    "event.ingested": "Document was processed.",

    "duplicateReason.rovnaky hash suboru": "same file hash",
    "duplicateReason.podobna firma/osoba": "similar company/person",
    "duplicateReason.podobny typ": "similar type",
    "duplicateReason.rovnaka alebo velmi podobna suma": "same or very similar amount",
    "duplicateReason.blizky datum dokumentu": "nearby document date",
    "duplicateReason.blizka expiracia": "nearby expiration date",

    "settings.eyebrow": "Configuration",
    "settings.title": "Settings",
    "settings.watchFolders": "Watch folders",
    "settings.noFolders": "No folders",
    "settings.folderPlaceholder": "/path/to/folder",
    "settings.add": "Add",
    "settings.mail": "Mail (optional)",
    "settings.enableMail": "Enable mail ingestion",
    "settings.imapHost": "IMAP host",
    "settings.port": "Port",
    "settings.username": "Username",
    "settings.password": "Password",
    "settings.telegram": "Telegram alerts",
    "settings.telegramDescription": "When a document is about to expire (insurance, contract, ID), Muninn will send a Telegram message.",
    "settings.enableTelegram": "Enable Telegram alerts",
    "settings.botToken": "Bot token (from @BotFather)",
    "settings.chatId": "Chat ID",
    "settings.notifyDays": "How many days in advance to alert",
    "settings.tokenStored": "The bot token is stored encrypted. Leave the field empty if you do not want to change it.",
    "settings.test": "Test",
    "settings.aiEngine": "AI engine",
    "settings.modeAuto": "Automatic (Claude/Codex CLI, then API key)",
    "settings.modeClaude": "Claude CLI only",
    "settings.modeCodex": "Codex CLI only",
    "settings.modeAnthropic": "Anthropic API key only",
    "settings.apiKey": "Anthropic API key (if needed)",
    "settings.testConnection": "Test connection",
    "settings.aiUsage": "AI usage",
    "settings.noProcessed": "No processed documents yet",
    "settings.processedDocuments": "Processed documents",
    "settings.tokenCosts": "API/Claude token costs",
    "settings.measuredTokens": "Measured tokens in/out",
    "settings.cliCalls": "CLI calls",
    "settings.provider": "Provider",
    "settings.documents": "Documents",
    "settings.costs": "Costs",
    "settings.tokens": "Tokens in/out",
    "settings.technicalStatus": "Technical status",
    "settings.aiMode": "AI mode",
    "settings.available": "available",
    "settings.missing": "missing",
    "settings.mailUidFailed": "Mail UID / failed",
    "settings.providerChain": "Provider chain",
    "settings.recentErrors": "Recent errors",
    "settings.noFailed": "No failed documents in the active DB.",
    "settings.recentJobs": "Recent jobs",
    "settings.refreshStatus": "Refresh status",
    "settings.privacyLink": "Privacy notice and AI processing",
    "settings.testError": "Error: {detail}",
  },
};

function detectInitialLanguage() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (SUPPORTED_LANGUAGES.includes(stored)) return stored;
  return "sk";
}

function interpolate(template, values = {}) {
  return template.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

function createTranslator(language) {
  return function translate(key, values) {
    const template = DICTIONARIES[language][key] ?? DICTIONARIES.sk[key];
    if (!template) return "";
    return interpolate(template, values);
  };
}

function skPlural(count, one, few, many) {
  if (count === 1) return one;
  if (count >= 2 && count <= 4) return few;
  return many;
}

function enPlural(count, one, many) {
  return count === 1 ? one : many;
}

function parseMetadata(event) {
  if (!event?.metadata_json) return {};
  try {
    return JSON.parse(event.metadata_json);
  } catch {
    return {};
  }
}

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [language, setLanguageState] = useState(detectInitialLanguage);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo(() => {
    const t = createTranslator(language);
    return {
      language,
      setLanguage: (next) => {
        if (SUPPORTED_LANGUAGES.includes(next)) setLanguageState(next);
      },
      toggleLanguage: () => setLanguageState((current) => (current === "sk" ? "en" : "sk")),
      t,
      dayUnit: (count) => (language === "sk" ? skPlural(count, "deň", "dni", "dní") : enPlural(count, "day", "days")),
      fileUnit: (count) => (language === "sk" ? skPlural(count, "súbor", "súbory", "súborov") : enPlural(count, "file", "files")),
      pageUnit: (count) => (language === "sk" ? skPlural(count, "stranu", "strany", "strán") : enPlural(count, "page", "pages")),
      documentUnit: (count) => (language === "sk" ? skPlural(count, "dokumente", "dokumentoch", "dokumentoch") : enPlural(count, "document", "documents")),
      savedViewLabel: (key, fallback) => t(`savedView.${key}.label`) || fallback || key,
      savedViewDescription: (key, fallback) => t(`savedView.${key}.description`) || fallback || "",
      reviewLabel: (value) => t(`review.${value}`) || value || "-",
      recurrenceLabel: (value) => (value ? t(`recurrence.${value}`) : t("common.none")),
      duplicateReason: (reason) =>
        (reason || "")
          .split(", ")
          .map((part) => t(`duplicateReason.${part}`) || part)
          .join(", "),
      eventMessage: (event) => {
        const metadata = parseMetadata(event);
        if (event.event_type === "review_status") {
          return t("event.review_status", { status: t(`review.${metadata.to}`) || metadata.to || "-" });
        }
        if (event.event_type === "retry_finished") {
          return t("event.retry_finished", { status: metadata.status || "-" });
        }
        if (event.event_type === "duplicate_warning") {
          return t("event.duplicate_warning", { count: metadata.candidates?.length ?? "-" });
        }
        return t(`event.${event.event_type}`) || event.message;
      },
    };
  }, [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}
