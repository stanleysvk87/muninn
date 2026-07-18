# Inštalácia

Dva nezávislé spôsoby nasadenia — vyber si jeden. Oba používajú ten istý
kód, ten istý dátový adresár (SQLite DB + archív súborov) a tie isté
premenné prostredia z `.env.example`.

> **Stav:** tento dokument sa dopĺňa priebežne s implementáciou (Fáza 5).
> Zatiaľ obsahuje kostru krokov, nie finálne overené príkazy.

## Predpoklady (oba spôsoby)

- Linux (testované na Debian/Ubuntu-based aj Armbian aarch64)
- Vygenerovať `MUNINN_ENCRYPTION_KEY` (na šifrovanie uloženého API kľúča),
  jednorazovo, uložiť do env súboru — nikdy do gitu
- Rozhodnúť: AI engine cez existujúci `claude`/`codex` CLI login (žiadne
  extra platenie, ale viazané na domovský priečinok konkrétneho
  používateľa), alebo cez Anthropic API kľúč (nezávislé od používateľa,
  vhodnejšie pre hardened/dedikovaný service account). Pozri
  ARCHITECTURE.md sekciu "AI engine".

## A) Docker

```
docker compose up -d
```

- Jeden kontajner, žiadny nginx/Caddy navyše.
- Dátový adresár a archív sa mountujú cez `.env` (nie je natvrdo v
  `docker-compose.yml`) — pozri `MUNINN_DATA_DIR` / `MUNINN_ARCHIVE_DIR`.
- Ak chceš CLI AI engine namiesto API kľúča, treba domountovať
  `~/.claude`/`~/.codex` credential súbory a samotný binárny CLI (funguje
  len ak kontajner beží na rovnakej CPU architektúre ako host).

*(TODO Fáza 5: presné docker-compose.yml sekcie, bootstrap prvého admin
účtu, príklad `.env`.)*

## B) systemd (bez Dockeru)

```
python -m venv venv && venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && npm run build
sudo cp systemd/muninn.service /etc/systemd/system/
sudo systemctl enable --now muninn
```

- Beží ako obyčajný proces pod `uvicorn`, `Type=simple`, `Restart=on-failure`.
- **Dôležité**: ak appka používa `claude`/`codex` CLI ako AI engine, service
  musí bežať pod tvojím vlastným (prihláseným) používateľom, nie pod
  dedikovaným hardened service accountom — CLI credentials sú v `~/.claude`
  toho konkrétneho používateľa. Ak chceš dedikovaný service account s plnou
  izoláciou (`NoNewPrivileges`, `ProtectSystem=strict`...), použi API kľúč
  namiesto CLI.

*(TODO Fáza 5: presný `muninn.service`, `muninn.env`, prvé spustenie.)*

## Mail ingestion (voliteľné, obe cesty nasadenia)

Appka funguje aj bez toho — mail polling je vypnutý defaultne. Ak chceš
automatické spracovanie mailových príloh:

1. Vytvoriť mailbox na existujúcom mailserveri (mimo tohto repa):
   `docker exec mailserver setup email add invoices@example.com <heslo>`
2. V appke, v Nastaveniach → Mail, zapnúť a zadať IMAP prihlasovacie údaje.

## Watch-folder

V Nastaveniach → Priečinky pridaj cestu k priečinku, ktorý appka bude
sledovať (napr. priečinok synchronizovaný cez Syncthing z telefónu).
Zmena sa prejaví okamžite, bez reštartu.
