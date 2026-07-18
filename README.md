# Muninn

Samostatne hostovaná archivácia dôležitých dokumentov — faktúry, zmluvy,
poistky, rodné listy, doklady, čokoľvek, čo chceš mať rýchlo dohľadateľné.
Dokument (foto, PDF, mailová príloha) príde do appky, prejde cez AI
extrakciu metadát (kto/čo dokument identifikuje, typ dokumentu, dátum,
suma, zhrnutie), uloží sa do archívu a dá sa neskôr nájsť jednoduchým
hľadaním (napr. "uniqa" nájde všetko od Uniqa, meno dieťaťa nájde jeho
rodný list).

Meno je po Muninovi, jednom z dvoch Odinových havranov (pamäť) — zapadá do
existujúceho pomenovania: Yggdrasil (server), Heimdall (ops dashboard),
Bifrost (discovery), Midgard (brand/web).

## Čo to robí

- **Príjem dokumentov** troma cestami: nahratie cez web UI (drag-drop alebo
  odfotenie mobilom priamo v prehliadači), sledovaný priečinok na disku, a
  voliteľne mailová schránka (príloha z mailu sa spracuje automaticky).
- **AI extrakcia**: model prečíta dokument a vráti hlavný identifikátor
  (firma pri faktúre/zmluve, meno osoby pri rodnom liste/doklade...), typ
  dokumentu, dátum, sumu (ak relevantná) a krátke zhrnutie. Používa buď
  existujúci Claude/Codex CLI login na stroji (žiadne extra platenie),
  alebo API kľúč zadaný v Nastaveniach, ak CLI nie je k dispozícii.
- **Archív + hľadanie**: súbory sa ukladajú do priečinkov podľa identifikátora,
  metadáta idú do SQLite s fulltextovým vyhľadávaním (FTS5) — zadáš meno a
  nájdeš všetko súvisiace.
- **Export**: filtrovaný výber dokumentov sa dá stiahnuť ako CSV/JSON/ZIP.

## Nasadenie

Beží ako **jeden proces** (FastAPI servíruje aj postavený frontend) — preto
sa dá spustiť buď ako jeden Docker kontajner, alebo ako jedna systemd
služba na hocijakom Linuxe, bez väzby na konkrétny stroj. Podrobný postup
pre oba spôsoby je v [INSTALL.md](INSTALL.md).

Architektonické rozhodnutia a zdôvodnenia sú v [ARCHITECTURE.md](ARCHITECTURE.md).

## Stav

Nasadené a v prevádzke na yggdrasil (Docker, port 8000). Pozri `docs/adr/`
pre architektonické rozhodnutia urobené počas stavby.

## Licencia

Apache-2.0, pozri [LICENSE](LICENSE).
