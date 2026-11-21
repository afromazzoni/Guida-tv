"""Guida Sport: scarica e normalizza gli eventi sportivi della settimana.

Fonti
  - Virgilio Sport guida TV  : 7 giorni, tutti i canali italiani (Sky, DAZN, Prime, Rai, Mediaset, Eurosport...)
  - Sky EPG (apid.sky.it)    : dirette sui canali Sky Sport 201-213, 251-259, DAZN 1-4 su Sky
  - ESPN scoreboard API      : NFL, NBA, NHL, college football (orari ufficiali, emittenti USA)
  - MLB Stats API            : MLB (tutte su MLB.tv)
  - HBO Max Sport (pagina)   : eventi Eurosport/HBO Max delle prossime ~36 ore, accumulati in cache

Uso:  python guida_sport.py            -> scrive site/events.json
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROME = ZoneInfo("Europe/Rome")
UTC = timezone.utc
DAYS = 7
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "events.json"
CACHE = ROOT / "data" / "hbo_cache.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
      "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"}
S = requests.Session()
S.headers.update(UA)

NOW_LOCAL = datetime.now(ROME)
TODAY = NOW_LOCAL.date()
WINDOW_END = TODAY + timedelta(days=DAYS)
WARN: list[str] = []


def log(*a, **kw):
    print(*a, file=sys.stderr, **kw)


def get(url, **kw):
    r = S.get(url, timeout=30, **kw)
    r.raise_for_status()
    return r


# ----------------------------------------------------------------------------- canali / emittenti
FREE = ("rai", "italia 1", "canale 5", "rete 4", "rete4", "tv8", "cielo", "20 mediaset", "sportitalia",
        "supertennis", "dmax", "nove", "la7", "mediaset", "raiplay", "sky tg24")


def provider(ch: str) -> str:
    c = ch.lower()
    if "eurosport" in c or "hbo" in c or "discovery" in c:
        return "hbo"
    if "dazn" in c or "game pass" in c:
        return "dazn"
    if "prime" in c or "amazon" in c:
        return "prime"
    if "disney" in c:
        return "disney"
    if "league pass" in c or "mlb.tv" in c:
        return "pass"
    if c.startswith("sky") or c.startswith("now"):
        return "sky"
    if any(c.startswith(f) or f in c for f in FREE):
        return "free"
    return "other"


def norm_channel(ch: str) -> str:
    ch = re.sub(r"\s+", " ", ch).strip()
    ch = re.sub(r"(?i)^sky sport uno$", "Sky Sport 1", ch)
    ch = re.sub(r"(?i)^dazn$", "DAZN", ch)
    ch = re.sub(r"(?i)^dazn ?(\d)$", r"DAZN \1", ch)
    ch = re.sub(r"(?i)^rai sport\s*$", "Rai Sport", ch)
    ch = re.sub(r"(?i)^cielo$", "Cielo", ch)
    ch = re.sub(r"(?i)^amazon prime video$", "Prime Video", ch)
    return ch


# ----------------------------------------------------------------------------- sport
def sport_from(sport: str, comp: str = "", title: str = "", extra: str = "") -> str:
    s, blob = sport.lower(), f"{comp} {title} {extra}".lower()
    if "nba" in blob.split() or re.search(r"\bnba\b", blob):
        return "NBA"
    if re.search(r"\bnfl\b", blob) or "football americano" in s and "college" not in blob:
        return "NFL"
    if re.search(r"\bnhl\b", blob):
        return "NHL"
    if re.search(r"\bmlb\b", blob) or s == "baseball":
        return "MLB"
    if "college" in blob and "football" in blob:
        return "College Football"
    if re.search(r"motogp|moto ?2\b|moto ?3\b|moto-e|motoe", blob) or s in ("motogp", "motomondiale", "motociclismo"):
        return "MotoGP"
    if re.search(r"formula ?1|\bf1\b", blob) or s in ("formula 1", "f1"):
        return "F1"
    m = {"calcio": "Calcio", "tennis": "Tennis", "basket": "Basket", "pallacanestro": "Basket",
         "volley": "Volley", "pallavolo": "Volley", "rugby": "Rugby", "golf": "Golf",
         "ciclismo": "Ciclismo", "ciclo-cross": "Ciclismo", "ciclocross": "Ciclismo",
         "sci alpino": "Sport invernali", "sci di fondo": "Sport invernali", "salto con sci": "Sport invernali",
         "biathlon": "Sport invernali", "combinata nordica": "Sport invernali", "snowboard": "Sport invernali",
         "pattinaggio di figura": "Sport invernali", "pattinaggio": "Sport invernali", "bob": "Sport invernali",
         "slittino": "Sport invernali", "sci": "Sport invernali", "freestyle": "Sport invernali",
         "motori": "Motori", "automobilismo": "Motori", "superbike": "Motori", "rally": "Motori",
         "boxe": "Combattimento", "pugilato": "Combattimento", "mma": "Combattimento", "ufc": "Combattimento",
         "wrestling": "Combattimento", "snooker": "Snooker", "freccette": "Freccette", "darts": "Freccette",
         "nuoto": "Nuoto", "atletica": "Atletica", "atletica leggera": "Atletica", "hockey": "Hockey",
         "hockey su ghiaccio": "Hockey", "pallamano": "Pallamano", "padel": "Padel", "equitazione": "Equitazione",
         "football americano": "NFL", "baseball": "MLB", "scherma": "Scherma", "badminton": "Altro",
         "tennistavolo": "Altro", "pallanuoto": "Pallanuoto", "vela": "Vela", "ippica": "Equitazione"}
    if s in m:
        return m[s]
    for k, v in m.items():
        if k in s:
            return v
    return sport.strip().capitalize() if sport.strip() else "Altro"


# ----------------------------------------------------------------------------- matching
GENERIC = set("""gara gare prove prova libere libera qualifiche qualifica sprint finale finali semifinale semifinali
quarti singolare singolari doppio doppi singles doubles manche partita match live diretta coppa mondo campionato
giornata serie league turno round sessione warm studio femminile maschile prima seconda terza quarta 1a 2a 3a
torneo world tour grand prix trofeo stagione 2026 2027 edizione speciale evento evento: contro della delle dello
degli","the and""".split())


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zà-ÿ0-9]+", text.lower())
    return {w for w in words if len(w) >= 4 and w not in GENERIC}


def chan_key(ch: str) -> str:
    return re.sub(r"[^a-z0-9]", "", norm_channel(ch).lower())


def mk_id(*parts) -> str:
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:10]


def event(start: datetime, sport: str, comp: str, title: str, channels: list[str], src: str, **extra) -> dict:
    loc = start.astimezone(ROME)
    chans = []
    for c in channels:
        c = norm_channel(c)
        if c and c not in chans:
            chans.append(c)
    return {"id": mk_id(src, loc.isoformat(), title), "start": loc.isoformat(timespec="minutes"),
            "date": loc.date().isoformat(), "time": loc.strftime("%H:%M"), "sport": sport,
            "comp": comp.strip(), "title": title.strip(), "channels": chans, "src": [src], **extra}


def in_window(dt: datetime) -> bool:
    d = dt.astimezone(ROME).date()
    return TODAY <= d < WINDOW_END


def minutes_apart(a: dict, b: dict) -> float:
    return abs((datetime.fromisoformat(a["start"]) - datetime.fromisoformat(b["start"])).total_seconds()) / 60


TEAM_SPORTS = {"Calcio", "Basket", "NBA", "NFL", "NHL", "MLB", "College Football", "Volley", "Rugby", "Hockey",
               "Pallanuoto", "Pallamano"}
VAGUE = {"Motori", "Altri", "Altro"}


def _dt(e: dict, k="start") -> datetime:
    return datetime.fromisoformat(e[k])


def time_ok(a: dict, b: dict, tol: int) -> bool:
    """Stesso orario (±tol) oppure l'inizio di uno cade dentro la diretta dell'altro
    (Sky fa partire il programma col pre-partita, Virgilio indica il calcio d'inizio)."""
    if minutes_apart(a, b) <= tol:
        return True
    for x, y in ((a, b), (b, a)):
        if x.get("end"):
            sx, ex, sy = _dt(x), _dt(x, "end"), _dt(y)
            if sx - timedelta(minutes=tol) <= sy <= min(ex - timedelta(minutes=15), sx + timedelta(minutes=130)):
                return True
    return False


def find_match(ev: dict, pool: list[dict], tol=20) -> dict | None:
    et = tokens(ev["title"] + " " + ev["comp"])
    ek = {chan_key(c) for c in ev["channels"]}
    best, best_score = None, 0
    for p in pool:
        if p is ev or not time_ok(ev, p, tol):
            continue
        tok = len(et & tokens(p["title"] + " " + p["comp"]))
        close = minutes_apart(ev, p) <= 10
        same_sport = ev["sport"] == p["sport"] or bool({ev["sport"], p["sport"]} & VAGUE)
        pk = {chan_key(c) for c in p["channels"]}
        chan = bool(pk & ek) or ("sky" in pk and any(provider(c) == "sky" for c in ev["channels"]))
        if tok and (same_sport or tok >= 2):
            score = tok * 2 + chan + close
        elif close and same_sport and ev["sport"] not in TEAM_SPORTS and chan:
            score = 1
        else:
            continue
        if score > best_score:
            best, best_score = p, score
    return best


def merge_into(dst: dict, src: dict, prefer_src_title=False):
    if dst["sport"] in VAGUE and src["sport"] not in VAGUE:
        dst["sport"] = src["sport"]
    if not dst["comp"] and src["comp"]:
        dst["comp"] = src["comp"]
    if src.get("end") and not dst.get("end"):
        dst["end"] = src["end"]
    for c in src["channels"]:
        if c not in dst["channels"]:
            dst["channels"].append(c)
    # "Sky" generico di Virgilio sostituito dal canale preciso
    if "Sky" in dst["channels"] and any(c.startswith("Sky ") for c in dst["channels"]):
        dst["channels"].remove("Sky")
    for s in src["src"]:
        if s not in dst["src"]:
            dst["src"].append(s)
    if prefer_src_title:
        dst["title"], dst["comp"], dst["sport"] = src["title"], src["comp"] or dst["comp"], src["sport"]
        dst["start"], dst["date"], dst["time"] = src["start"], src["date"], src["time"]
    for k in ("us", "teams", "live"):
        if k in src and k not in dst:
            dst[k] = src[k]


# ----------------------------------------------------------------------------- Virgilio
MESI = {m: i for i, m in enumerate("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")


def fetch_virgilio() -> list[dict]:
    t = get("https://www.virgilio.it/sport/guida-tv/").text
    out = []
    parts = re.split(r"<h2[^>]*>", t)
    for part in parts[1:]:
        head = strip_tags(part.split("</h2>", 1)[0])
        m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", head.lower())
        if not m or m.group(2) not in MESI:
            continue
        day = datetime(int(m.group(3)), MESI[m.group(2)], int(m.group(1))).date()
        body = part.split("</h2>", 1)[1]
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 3:
                continue
            tm = re.search(r"(\d{1,2})[:.](\d{2})", strip_tags(cells[0]))
            if not tm:
                continue
            desc = cells[1]
            sm = re.search(r"<strong>(.*?)</strong>", desc, re.S)
            sport = strip_tags(sm.group(1)).strip() if sm else ""
            rest = desc[sm.end():] if sm else desc
            if "<br" in rest:
                comp_raw, title_raw = re.split(r"<br\s*/?>", rest, maxsplit=1)
            else:
                comp_raw, title_raw = "", rest
            comp = re.sub(r"^[\s,]+|[\s:]+$", "", strip_tags(comp_raw))
            title = re.sub(r"\s+", " ", strip_tags(title_raw)).strip(" :")
            if not title:
                title, comp = comp, ""
            chans = [c.strip() for c in strip_tags(cells[-1]).split(",") if c.strip()]
            start = datetime(day.year, day.month, day.day, int(tm.group(1)), int(tm.group(2)), tzinfo=ROME)
            if not in_window(start):
                continue
            sp = sport_from(sport, comp, title)
            out.append(event(start, sp, comp, title, chans, "virgilio"))
    log(f"virgilio: {len(out)} eventi")
    return out


# ----------------------------------------------------------------------------- Sky EPG
SKY_NUMBERS = set(range(201, 210)) | {211, 212, 213, 214, 215, 216, 217, 227} | set(range(251, 260))
SKY_SHOWS = re.compile(r"(?i)paddock|studio|pre ?partita|post ?partita|debriefing|notebook|zona rossa|insider|"
                       r"\bgrid\b|race anatomy|calcio show|calcio club|\bclub\b|\btg\b|highlights|magazine|"
                       r"\bshow\b|speciale|conferenza|anteprima|pit ?lane|pre ?gara|post ?gara|prima di|"
                       r"sky sport 24|reloaded|best of|i gol|tutti i gol|pre ?game|post ?game|room|talk|ep\.\s*\d|"
                       r"l'originale|servito|\d{2}/\d{2}/\d{4}|conf\. stampa|rassegna")


def fetch_sky() -> list[dict]:
    chans = get("https://apid.sky.it/gtv/v1/channels?env=DTH").json()
    if isinstance(chans, dict):
        chans = next(v for v in chans.values() if isinstance(v, list))
    sel = {c["id"]: c for c in chans if c.get("number") in SKY_NUMBERS}
    ids = ",".join(str(i) for i in sel)
    out = []
    for d in range(DAYS):
        day = TODAY + timedelta(days=d)
        a = datetime(day.year, day.month, day.day, tzinfo=ROME).astimezone(UTC)
        b = a + timedelta(days=1) - timedelta(seconds=1)
        page, evs = 0, []
        while True:
            url = (f"https://apid.sky.it/gtv/v1/events?from={a:%Y-%m-%dT%H:%M:%SZ}&to={b:%Y-%m-%dT%H:%M:%SZ}"
                   f"&pageSize=999&pageNum={page}&env=DTH&channels={ids}")
            j = get(url).json()
            evs += j.get("events", [])
            if len(evs) >= j.get("total", 0) or not j.get("events"):
                break
            page += 1
        for e in evs:
            if e.get("programHighlights") != "L":
                continue
            title = (e.get("eventTitle") or "").strip()
            syn = e.get("eventSynopsis") or ""
            if not title or SKY_SHOWS.search(title) or re.fullmatch(r"[\d/ .-]+", title):
                continue
            if re.match(r"(?i)un approfondimento", syn) or re.search(r"(?i)\.\s*-\s*(pre|post) ?partita\s*$", syn):
                continue
            # giocatori dalla sinossi quando il titolo non li ha ("Singolare: Finale" -> "... · Sinner/Alcaraz")
            pm = re.search(r"\.\s*([A-Z][\w'\-]+(?: [A-Z][\w'\-]+)?/[A-Z][\w'\-]+(?: [A-Z][\w'\-]+)?)\s*(?:\(|$)", syn)
            if pm and " - " not in title and pm.group(1).split("/")[0] not in title:
                title = f"{title} · {pm.group(1).replace('/', ' - ')}"
            start = datetime.fromisoformat(e["starttime"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(e["endtime"].replace("Z", "+00:00"))
            if (end - start) < timedelta(minutes=20) or not in_window(start):
                continue
            ch = e.get("channel") or {}
            num = ch.get("number")
            name = ch.get("name") or ""
            if 251 <= (num or 0) <= 259:
                name = f"Sky Sport {num}"
            sub = ((e.get("content") or {}).get("subgenre") or {}).get("name", "")
            extra = f"{name} {syn[:250]}"
            if num == 207:
                extra += " F1"
            if num == 208:
                extra += " MotoGP"
            sp = sport_from(sub, "", title, extra)
            comp = ""
            mc = re.search(r"(?i)\b(MotoGP|Moto2|Moto3|MotoE|F1|F2|F3|F1 Academy|Formula E|NBA|Serie A|Serie B|"
                           r"Serie C|Serie D|Coppa Italia|Premier League|Bundesliga|Ligue 1|LaLiga|Liga|Champions League|Europa League|"
                           r"Conference League|Eurolega|EuroLeague|ATP Finals|ATP|WTA|Davis Cup|Coppa Davis|"
                           r"Billie Jean King Cup|Serie A Basket|LBA|Superbike|WRC|NASCAR|IndyCar|MLS)\b", syn)
            if mc:
                comp = mc.group(1)
            if sp == "MotoGP" and comp in ("Moto2", "Moto3", "MotoE") and comp not in title:
                title = f"{comp} · {title}"
            if sp == "F1" and comp in ("F2", "F3", "F1 Academy") and comp not in title:
                title = f"{comp} · {title}"
            out.append(event(start, sp, comp, title, [name], "sky", live=True, desc=syn[:220],
                             end=end.astimezone(ROME).isoformat(timespec="minutes")))
    log(f"sky: {len(out)} dirette")
    return out


# ----------------------------------------------------------------------------- ESPN (NFL, NBA, NHL, CFB)
ESPN_FAMILY = {"espn", "espn2", "espnu", "espn+", "abc", "sec network", "secn+", "acc network", "accnx",
               "espnews", "disney+", "hulu", "espn unlimited", "espn deportes", "longhorn network"}
ESPN_LEAGUES = [
    ("football", "nfl", "NFL", "NFL", ""),
    ("basketball", "nba", "NBA", "NBA", ""),
    ("hockey", "nhl", "NHL", "NHL", ""),
    ("football", "college-football", "College Football", "NCAA Football", "&groups=80"),
]


def fetch_espn() -> list[dict]:
    out = []
    for sport, league, label, comp_default, extra in ESPN_LEAGUES:
        raw, seen = [], set()
        for d in range(-1, DAYS + 1):  # giorni USA: la sera USA è notte in Italia
            day = (TODAY + timedelta(days=d)).strftime("%Y%m%d")
            try:
                j = get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
                        f"?dates={day}&limit=500{extra}").json()
            except Exception as ex:
                WARN.append(f"ESPN {label} {day}: {ex}")
                continue
            for e in j.get("events", []):
                if e["id"] not in seen:
                    seen.add(e["id"])
                    raw.append(e)
        n = 0
        for e in raw:
            start = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            if not in_window(start):
                continue
            comp = e["competitions"][0]
            teams = {c.get("homeAway"): c["team"] for c in comp.get("competitors", [])}
            if "home" not in teams or "away" not in teams:
                continue
            us = []
            for bc in comp.get("broadcasts", []):
                for nm in bc.get("names", []):
                    if nm not in us:
                        us.append(nm)
            espn = any(x.lower() in ESPN_FAMILY for x in us)
            if label == "NFL":
                chans = ["DAZN (NFL Game Pass)"]
            elif label == "NBA":
                chans = ["NBA League Pass"]
            elif label == "NHL":
                chans = ["Disney+"] if espn else []
            else:  # College football: solo le partite ESPN/ABC arrivano su Disney+
                if not espn:
                    continue
                chans = ["Disney+"]
            ht, at = teams["home"], teams["away"]
            title = f"{at.get('displayName')} @ {ht.get('displayName')}"
            nick = [t.get("name") or t.get("shortDisplayName") or "" for t in (at, ht)]
            week = (e.get("week") or {}).get("number")
            cmp = comp_default + (f" · Week {week}" if week and label in ("NFL", "College Football") else "")
            notes = [x.get("headline") for x in comp.get("notes", []) if x.get("headline")]
            if notes:
                h = notes[0]
                cmp = "NBA Cup" if "NBA Cup" in h else cmp + " · " + h
            state = e.get("status", {}).get("type", {}).get("state")
            out.append(event(start, label, cmp, title, chans, "espn", us=us,
                             teams=[t for t in nick if t], state=state))
            n += 1
        log(f"espn {label}: {n}")
    return out


def fetch_mlb() -> list[dict]:
    out = []
    j = get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={TODAY - timedelta(days=1)}"
            f"&endDate={WINDOW_END}").json()
    for d in j.get("dates", []):
        for g in d.get("games", []):
            start = datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00"))
            if not in_window(start):
                continue
            at, ht = g["teams"]["away"]["team"]["name"], g["teams"]["home"]["team"]["name"]
            gt = {"S": "Spring Training", "E": "Exhibition", "F": "Wild Card", "D": "Division Series",
                  "L": "LCS", "W": "World Series", "A": "All-Star Game"}.get(g.get("gameType"), "MLB")
            out.append(event(start, "MLB", gt, f"{at} @ {ht}", ["MLB.tv"], "mlb",
                             teams=[at.split()[-1], ht.split()[-1]]))
    log(f"mlb: {len(out)}")
    return out


# ----------------------------------------------------------------------------- HBO Max / Eurosport
def fetch_hbo() -> list[dict]:
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    try:
        t = get("https://www.hbomax.com/it/it/sports").text
        dec = json.JSONDecoder()
        for m in re.finditer(r'\{"__typename":"Event"', t):
            try:
                obj, _ = dec.raw_decode(t, m.start())
            except ValueError:
                continue
            sd = (obj.get("scheduleDates") or {}).get("startDate")
            if not sd:
                continue
            cache[obj.get("hbomaxId") or mk_id(sd, obj.get("title"))] = {
                "start": sd, "end": (obj.get("scheduleDates") or {}).get("endDate"),
                "title": (obj.get("title") or {}).get("full") or "",
                "short": (obj.get("title") or {}).get("short") or "",
                "sport": obj.get("sport") or "", "league": obj.get("league") or "",
                "summary": ((obj.get("summary") or {}).get("full") or "")[:220],
                "url": obj.get("url") or ""}
    except Exception as ex:
        WARN.append(f"HBO Max: {ex}")
    # pulizia: via gli eventi passati
    cutoff = datetime(TODAY.year, TODAY.month, TODAY.day, tzinfo=ROME).astimezone(UTC)
    cache = {k: v for k, v in cache.items() if datetime.fromisoformat(v["start"].replace("Z", "+00:00")) >= cutoff}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    out = []
    for v in cache.values():
        start = datetime.fromisoformat(v["start"].replace("Z", "+00:00"))
        if not in_window(start):
            continue
        sp = sport_from(v["sport"], v["short"], v["title"])
        title = v["title"] or v["short"]
        comp = v["short"] if v["short"] and v["short"] not in title else ""
        if v["sport"] and sp in ("Sport invernali", "Altro", "Ciclismo", "Motori"):
            comp = (v["sport"] + (" · " + comp if comp else "")).strip()
        link = "https://www.hbomax.com" + v["url"] if v["url"].startswith("/") else ""
        out.append(event(start, sp, comp, title, ["HBO Max"], "hbo", live=True, desc=v["summary"], link=link))
    log(f"hbo: {len(out)} (cache {len(cache)})")
    return out


# ----------------------------------------------------------------------------- unione
def build() -> dict:
    sources = {}
    for name, fn in [("virgilio", fetch_virgilio), ("sky", fetch_sky), ("espn", fetch_espn),
                     ("mlb", fetch_mlb), ("hbo", fetch_hbo)]:
        try:
            sources[name] = fn()
        except Exception as ex:
            WARN.append(f"{name}: {ex}")
            log(f"ERRORE {name}: {ex}")
            sources[name] = []

    events = list(sources["virgilio"])

    # Sky: arricchisce Virgilio (canale preciso) o aggiunge le dirette mancanti
    for e in sources["sky"]:
        m = find_match(e, events, tol=20)
        if m:
            merge_into(m, e)
            if "desc" not in m and e.get("desc"):
                m["desc"] = e["desc"]
        else:
            events.append(e)

    # Sport USA: l'evento ESPN/MLB diventa quello di riferimento, assorbendo i duplicati
    for e in sources["espn"] + sources["mlb"]:
        nick = [n.lower() for n in e.get("teams", [])]
        dup = [p for p in events if minutes_apart(e, p) <= 90 and nick
               and all(n in (p["title"] + " " + p.get("desc", "")).lower() for n in nick)]
        for p in dup:
            merge_into(e, p)
            if "desc" in p and "desc" not in e:
                e["desc"] = p["desc"]
            events.remove(p)
        if not e["channels"]:
            e["channels"] = ["Nessun canale in Italia"]
        events.append(e)

    # HBO Max / Eurosport
    for e in sources["hbo"]:
        m = find_match(e, [p for p in events if p["sport"] == e["sport"] or
                           any(provider(c) == "hbo" for c in p["channels"])], tol=25)
        if m:
            merge_into(m, e)
            if e.get("link"):
                m["link"] = e["link"]
        else:
            events.append(e)

    # ultimo passaggio: stesso orario, stesso sport individuale, stessa competizione -> un solo evento
    events.sort(key=lambda x: (x["start"], x["sport"]))
    i = 0
    while i < len(events):
        a = events[i]
        j = i + 1
        while j < len(events) and events[j]["start"] == a["start"]:
            b = events[j]
            same = (a["sport"] == b["sport"] and a["sport"] not in TEAM_SPORTS
                    and (a["comp"].lower() == b["comp"].lower() or tokens(a["comp"]) & tokens(b["comp"])
                         or tokens(a["title"]) & tokens(b["title"])))
            if same:
                if len(b["title"]) > len(a["title"]) and " - " in b["title"]:
                    a["title"] = b["title"]
                merge_into(a, b)
                events.pop(j)
            else:
                j += 1
        i += 1

    # Eurosport è dentro HBO Max
    for e in events:
        if any("eurosport" in c.lower() for c in e["channels"]) and "HBO Max" not in e["channels"]:
            e["channels"].append("HBO Max")
        e["chp"] = [provider(c) if c != "Nessun canale in Italia" else "none" for c in e["channels"]]
        e["providers"] = sorted(set(e["chp"]) - {"none"}) or ["none"]
        # Sky Sport 4K non è su NOW; tutti gli altri canali Sky Sport sì (251-259 come eventi singoli)
        e["now"] = any(p == "sky" and "4k" not in c.lower() for c, p in zip(e["channels"], e["chp"]))

    events.sort(key=lambda x: (x["start"], x["sport"], x["title"]))
    days = [(TODAY + timedelta(days=i)).isoformat() for i in range(DAYS)]
    return {"generated": datetime.now(ROME).isoformat(timespec="minutes"), "days": days,
            "counts": {k: len(v) for k, v in sources.items()}, "warnings": WARN, "events": events}


SKELETON_HEAD = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
</head>
<body>
"""


def build_index():
    """site/index.html per GitHub Pages: la stessa pagina dell'artifact, con lo scheletro HTML completo."""
    src = ROOT / "site" / "guida-sport.html"
    (ROOT / "site" / "index.html").write_text(SKELETON_HEAD + src.read_text(encoding="utf-8") + "\n</body>\n</html>\n",
                                             encoding="utf-8")


def main():
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    build_index()
    from collections import Counter
    log(f"\nTotale {len(data['events'])} eventi -> {OUT}")
    log("per sport:", dict(Counter(e["sport"] for e in data["events"]).most_common()))
    log("per emittente:", dict(Counter(p for e in data["events"] for p in e["providers"]).most_common()))
    if WARN:
        log("AVVISI:", *WARN, sep="\n  ")


if __name__ == "__main__":
    main()
