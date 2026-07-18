# Architektúra

## Prehľad

Jeden Python proces (FastAPI) servíruje API aj postavený React frontend.
Žiadny nginx/Caddy medzičlánok — SPA fallback a kompresia riešené priamo
v `main.py`. Dôvod: aby sa dalo appku spustiť rovnako jednoducho ako jeden
Docker kontajner alebo jednu systemd službu, bez závislosti na reverse
proxy, na hocijakom Linuxe.

```
                    ┌─────────────────────────────┐
  foto/PDF ────────▶│   watch-folder (watchdog)   │
  mail príloha ─────▶│   IMAP poller (voliteľné)   ├──▶ ingest/pipeline.py
  web upload ───────▶│   POST /api/upload          │         │
                    └─────────────────────────────┘         ▼
                                                    ai_engine (claude/codex
                                                    CLI alebo API kľúč)
                                                             │
                                                             ▼
                                              archiv/<firma>/ + SQLite
                                                             │
                                                             ▼
                                          FTS5 fulltextové hľadanie ◀── web UI
```

## Kľúčové rozhodnutia (a odchýlky od Heimdallu)

Heimdall (`/opt/heimdall`) je najbližší existujúci vzor v tomto homelabe
(FastAPI + React, session-cookie auth s CSRF). Muninn preberá čo dáva
zmysel, ale odchyľuje sa tam, kde to vyžaduje účel appky:

- **SQLite + FTS5 namiesto flat JSON súborov.** Heimdall nemá databázu,
  persistuje do `app/data/*.json` cez atomický write helper — funguje to
  pre dashboardy, ale Muninn potrebuje reálne fulltextové vyhľadávanie
  naprieč rastúcim archívom, čo flat JSON nevie. SQLite je stále jeden
  súbor, žiadna extra služba (žiadny Postgres), rovnako prenositeľné.
- **Jeden proces, žiadny nginx/Caddy.** Heimdall beží ako 3 kontajnery
  (backend, frontend+nginx, voliteľný Caddy). Muninn to zjednodušuje na
  jeden proces práve kvôli požiadavke "Docker aj systemd, na hocijakom
  Linuxe" — s reverse proxy navyše by to vyžadovalo viac pohyblivých častí
  pri systemd nasadení.
- **`watchdog` (Python knižnica) namiesto `inotifywait`.** Žiadna extra
  apt závislosť v Docker image, funguje identicky pod systemd.
- **Bezpečnosť AI extrakcie**: dokument môže byť od cudzej strany (faktúra
  od dodávateľa) a môže obsahovať text snažiaci sa manipulovať model
  (prompt injection). Preto AI volanie dostane prístup **len na čítanie
  jedného konkrétneho súboru** (izolovaný dočasný priečinok na jeden
  spracovávaný dokument, nikdy celý inbox/watch-folder), nikdy Bash/Write.
  Presun súboru do archívu a zápis do DB robí vždy backend kód na základe
  naparsovaného JSON od modelu, nikdy priamo model.

## AI engine — výber providera

`ai_engine.get_provider()` vyberie v tomto poradí:
1. `claude` CLI (`~/.local/bin/claude`) ak je nájdený a prihlásený —
   headless `claude -p`, pod existujúcim predplatným, žiadne extra
   platenie.
2. `codex` CLI ak je `claude` nedostupný.
3. Anthropic API kľúč zadaný v Nastaveniach (šifrovaný na disku cez
   Fernet), ak ani jeden CLI nie je k dispozícii.

Dôležitý detail pri `claude -p`: prompt musí byť **hneď za `-p`**, pred
ostatnými flagmi (`--add-dir`, `--allowedTools` sú variadické a zožerú
nasledujúci argument ako svoju vlastnú hodnotu, čím appke zmizne prompt).
Overené na prototype v `~/scripts/dokumenty/`.

## Model — odporúčania

- **Extrakcia metadát z dokumentu** (hlavná úloha): Sonnet 5 ako default.
  Beží bez dohľadu na reálnych (často neporiadnych) dokumentoch — presnosť
  je dôležitejšia než cena, lebo zlá extrakcia = nenájditeľný dokument.
  Haiku dostupný ako voliteľný "rýchly režim" v Nastaveniach.
- **"Test AI pripojenia" v Nastaveniach**: Haiku 4.5 — triviálna, rýchla
  úloha, nič viac.
- **Zlučovanie duplicitných firiem** (napr. "UNIQA poisťovňa" vs "Uniqa
  a.s.", plánovaná funkcia): Sonnet 5 s možnosťou eskalácie na Opus 4.8,
  ak presnosť zlučovania nebude stačiť — zlé automatické zlúčenie je
  deštruktívnejšie než zlá jednotlivá extrakcia.

## Dátový model

Pozri `backend/app/schema.sql` (vzniká vo Fáze 2) — tabuľky `users`,
`sessions`, `settings` (JSON key/value), `documents` + `documents_fts`
(FTS5 virtuálna tabuľka napojená triggermi).

## Fázy budovania

1. Scaffold + dokumentácia (tento commit)
2. Backend core — config, DB, auth (session cookie + CSRF, PBKDF2 heslá)
3. Ingestion pipeline — ai_engine, upload endpoint, watch-folder, mail
   poller (voliteľný), documents API + FTS5 hľadanie
4. Frontend — React/Vite, MidgardNet dizajnové tokeny, upload/search/
   detail/settings stránky
5. Deploy balenie — Dockerfile + docker-compose.yml, systemd unit,
   INSTALL.md pre oba spôsoby
6. GitHub private repo
