# Guida Sport

Guida TV settimanale dello sport, con filtri per giorno e sport. Nasce perché l'app NOW (Sky Italia) non ha una EPG: mostra solo il programma attuale e il successivo.

## Piano concordato (21 nov 2026)

- **Fonte principale:** https://www.virgilio.it/sport/guida-tv/ — giorno per giorno, ~7 giorni avanti, con orario, evento e canale (Sky Sport, DAZN, Prime, canali in chiaro).
- **Riscontro:** articoli "programmazione" / "guida tv" su sport.sky.it (es. weekend Premier League/Bundesliga).
- **Fonti scartate:** guidatv.sky.it (reindirizza a programmi.sky.it, solo catalogo, nessuna EPG); sorrisi.com (solo oggi); superguidatv (404); sportface.it (403 agli accessi automatici).
- **Script Python:** scarica e normalizza gli eventi (giorno, ora, sport, competizione, evento, canale) e assegna l'emittente: Sky/NOW, DAZN, Prime, in chiaro.
- **Pagina:** pagina web privata online (Artifact claude.ai), da aprire su telefono o PC. Filtri per giorno e per sport, toggle "solo su NOW", ricerca per squadra o pilota.
- **Sport in evidenza:** calcio, F1, MotoGP, tennis, NBA, MLB.
- **Aggiornamento:** automatico ogni giorno.

## Implementazione (21 nov 2026)

- `guida_sport.py` → `site/events.json`; pagina `site/guida-sport.html` pubblicata su https://claude.ai/artifact/5WqjU2RZWcFdnXov67Qc8V (con `events.json` come file allegato).
- Fonti aggiunte: EPG Sky `apid.sky.it/gtv/v1` (solo `programHighlights == "L"` = diretta; canali 201–217, 227, 251–259); ESPN scoreboard (NFL, NBA, NHL, college football, una richiesta per giorno, l'intervallo di date dà 400); MLB Stats API; pagina pubblica hbomax.com/it/it/sports (solo ~36 ore, accumulata in `data/hbo_cache.json`).
- Eurosport non è più su Sky; eurosport.it risponde 403. L'API GraphQL di HBO non va usata (bloccata dai permessi).
- Emittenti: NFL → DAZN (Game Pass); NBA → League Pass (+ Sky se presente); NHL/CFB → Disney+ se la partita è ESPN/ABC negli USA; MLB → MLB.tv; Eurosport → anche HBO Max.
- `aggiorna.ps1`: script + `claude -p` per ripubblicare; attività pianificata Windows "Guida Sport - aggiornamento" ogni giorno alle 12:00. Log in `data/aggiorna.log`.

## Convenzioni

- Terminologia sportiva in inglese (NL East, RBI, mph...), l'italiano solo come chiarimento.
- I canali Sky Sport 251–259 su NOW compaiono come singoli eventi nella sezione Sport dell'app.
- Le partite di Serie A solo su DAZN non sono su NOW.
