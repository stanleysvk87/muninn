# Inštalácia

Dva nezávislé spôsoby nasadenia — vyber si jeden. Oba používajú ten istý
kód (jeden proces servíruje API aj frontend, žiadny nginx/Caddy), ten istý
dátový adresár (SQLite DB + archív súborov) a tie isté premenné prostredia
z `.env.example`. Oba spôsoby boli reálne otestované (Docker cez
`docker compose up` + bootstrap/upload/reštart/perzistencia; systemd unit
overený `systemd-analyze verify`).

## Predpoklady (oba spôsoby)

- Linux (testované na Debian/Ubuntu-based aj Armbian aarch64)
- Vygenerovať `MUNINN_ENCRYPTION_KEY` (na šifrovanie uloženého API kľúča),
  jednorazovo, uložiť do env súboru — nikdy do gitu:
  ```
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- Rozhodnúť: AI engine cez existujúci `claude`/`codex` CLI login (žiadne
  extra platenie, ale viazané na domovský priečinok konkrétneho
  používateľa), alebo cez Anthropic API kľúč (nezávislé od používateľa,
  vhodnejšie pre hardened/dedikovaný service account). Pozri
  ARCHITECTURE.md sekciu "AI engine".

## A) Docker

```
cp .env.example .env
# uprav .env: MUNINN_ENCRYPTION_KEY (povinné), MUNINN_PORT, prípadne
# MUNINN_DATA_HOST_PATH / MUNINN_ARCHIVE_HOST_PATH ak nechceš ./data a ./archive
docker compose up -d
```

- Jeden kontajner (`docker ps` ukáže len `muninn-muninn-1`), žiadny nginx/
  Caddy navyše.
- Dátový adresár a archív sa mountujú cez `.env` (`MUNINN_DATA_HOST_PATH`/
  `MUNINN_ARCHIVE_HOST_PATH`, default `./data` a `./archive`) — nie sú
  natvrdo v `docker-compose.yml`.
- Overené: `docker compose up -d` → `curl localhost:8000/api/health` → 200,
  bootstrap prvého účtu cez `POST /api/auth/bootstrap`, upload dokumentu,
  `docker compose restart` → session aj dokument prežili (SQLite je na
  bind-mountnutom volume, nie vo vrstve kontajnera).
- Ak chceš CLI AI engine namiesto API kľúča, odkomentuj v
  `docker-compose.yml` mount `~/.claude`/`~/.codex` a binárku CLI (funguje
  len ak kontajner beží na rovnakej CPU architektúre ako host — pozri
  poznámku v `docker-compose.yml`).

## B) systemd (bez Dockeru)

```
python3 -m venv /opt/muninn/backend/venv
/opt/muninn/backend/venv/bin/pip install -r backend/requirements.txt
# skopíruj backend/app do /opt/muninn/backend/app

cd frontend && npm install && npm run build
# skopíruj frontend/dist do /opt/muninn/frontend/dist

sudo mkdir -p /etc/muninn
sudo cp systemd/muninn.env.example /etc/muninn/muninn.env
sudo chmod 600 /etc/muninn/muninn.env
# uprav /etc/muninn/muninn.env: MUNINN_ENCRYPTION_KEY (povinné)

sudo cp systemd/muninn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now muninn
```

- Beží ako obyčajný proces pod `uvicorn`, `Type=simple`, `Restart=on-failure`.
- Unit súbor prešiel `systemd-analyze verify` (jediná hláška je očakávaná
  — chýbajúca binárka, kým `/opt/muninn` reálne nevznikne).
- **Dôležité**: ak appka používa `claude`/`codex` CLI ako AI engine, service
  musí bežať pod tvojím vlastným (prihláseným) používateľom, nie pod
  dedikovaným hardened service accountom — CLI credentials sú v `~/.claude`
  toho konkrétneho používateľa. Ak chceš dedikovaný service account s plnou
  izoláciou (`NoNewPrivileges`, `ProtectSystem=strict`...), použi API kľúč
  namiesto CLI — pozri zakomentovaný blok v `systemd/muninn.service`.

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
