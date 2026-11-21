# Guida Sport

Guida TV settimanale dello sport in Italia, con filtri per giorno, sport ed emittente, ricerca per squadra o pilota e il filtro "Solo su NOW".

Ogni giorno GitHub Actions esegue `guida_sport.py`, salva `site/events.json` e pubblica la cartella `site/` su GitHub Pages.

## Fonti

- Virgilio Sport guida TV: 7 giorni, tutti i canali italiani
- EPG Sky: dirette sui canali Sky Sport e DAZN su Sky
- ESPN: NFL, NBA, NHL, college football
- MLB Stats API: MLB
- HBO Max Sport: eventi Eurosport delle prossime ~36 ore, accumulati in `data/hbo_cache.json`

## Uso locale

```
pip install -r requirements.txt
python guida_sport.py
```

Poi apri `site/index.html` con un server locale (`python -m http.server -d site`): aprendo il file direttamente il browser blocca il caricamento di `events.json`.
