# ADR 0001: SQLite + FTS5 namiesto flat JSON store

## Kontext

Heimdall (`/opt/heimdall`), najbližší existujúci vzor v tomto homelabe,
nepoužíva databázu — persistuje do `app/data/*.json` cez atomický write
helper (`core/json_store.py`). Funguje to dobre pre dashboardy a
konfiguráciu, kde sa číta/zapisuje podľa známeho kľúča.

Muninn potrebuje niečo iné: fulltextové vyhľadávanie naprieč rastúcim
archívom dokumentov ("nájdi všetko od Uniqa"), čo flat JSON súbory
neponúkajú bez toho, aby sme si vyhľadávanie napísali od nuly.

## Rozhodnutie

Použiť SQLite s FTS5 virtuálnou tabuľkou (`documents_fts`), napojenou
triggermi na hlavnú tabuľku `documents`. Do tej istej SQLite DB ide aj
`users`, `sessions`, `settings` — jeden súbor, nie kombinácia SQLite +
JSON.

## Dôsledky

- Stále jeden súbor, žiadna extra služba (žiadny Postgres/Elasticsearch),
  rovnako prenositeľné ako Heimdallov prístup.
- FTS5 je súčasť štandardnej Python `sqlite3` knižnice (overené na tomto
  hostiteľovi) — žiadna nová systémová závislosť.
- Odchýlka od house convention je vedomá a lokálna k tomuto projektu —
  nemení nič na Heimdalli ani inde.
