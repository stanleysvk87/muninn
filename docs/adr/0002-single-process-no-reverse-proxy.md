# ADR 0002: Jeden proces, žiadny nginx/Caddy

## Kontext

Heimdall beží ako 3 kontajnery (backend, frontend+nginx, voliteľný Caddy
pre TLS). Požiadavka na Muninn je ale byť spustiteľný rovnako jednoducho
ako Docker kontajner alebo ako systemd služba na hocijakom Linuxe — čím
viac pohyblivých častí (reverse proxy, viac kontajnerov), tým zložitejšie
je to zreplikovať mimo Dockeru.

## Rozhodnutie

FastAPI backend servíruje priamo aj postavený React frontend (`StaticFiles`
+ catch-all route pre SPA fallback + GZip middleware + cache headery pre
hashované assety). Jeden proces, jeden port.

## Dôsledky

- Docker nasadenie: 1 kontajner namiesto 3.
- systemd nasadenie: 1 unit súbor, `uvicorn main:app`, žiadny nginx config
  navyše.
- Kto chce TLS terminovanie, môže si pred appku dať vlastný reverse proxy
  (rovnako ako Heimdallov voliteľný Caddy profil) — to je mimo appky
  samotnej, nie jej súčasť.
- Nutné dávať pozor na `--workers 1` (nie viac) — watch-folder observer aj
  mail poller bežia v tom istom procese ako web server; viac workerov by
  znamenalo duplicitné spracovanie tých istých udalostí.
