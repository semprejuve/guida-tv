import gzip
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROME_TZ = ZoneInfo("Europe/Rome")
BR_TZ = ZoneInfo("America/Sao_Paulo")
NOW = datetime.now(ROME_TZ)
MIN_DT = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
MAX_DT = NOW + timedelta(days=7)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

PAESI_TV = {
    "Italia": {
        "epg_url": "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
        "canali": {
            "Rai 1": {"alias": ["rai 1", "rai1", "rai 1 hd"], "link": "https://www.raiplay.it/dirette/rai1"},
            "Rai 2": {"alias": ["rai 2", "rai2", "rai 2 hd"], "link": "https://www.raiplay.it/dirette/rai2"},
            "Rai 3": {"alias": ["rai 3", "rai3", "rai 3 hd"], "link": "https://www.raiplay.it/dirette/rai3"},
            "Rai Sport": {"alias": ["rai sport", "raisport", "rai sport hd"], "link": "https://www.raiplay.it/dirette/raisport"},
            "Canale 5": {"alias": ["canale 5", "canale5", "canale 5 hd"], "link": "https://mediasetinfinity.mediaset.it/diretta/canale5_cC5"},
            "Italia 1": {"alias": ["italia 1", "italia1", "italia 1 hd"], "link": "https://mediasetinfinity.mediaset.it/diretta/italia1_cI1"},
            "20 Mediaset": {"alias": ["20 mediaset", "20mediaset", "20", "venti", "20 hd"], "link": "https://mediasetinfinity.mediaset.it/diretta/20mediaset_cLB"},
            "TV8": {"alias": ["tv8", "tv 8", "tv8 hd"], "link": "https://tv8.it/streaming"},
            "Cielo": {"alias": ["cielo", "cielo hd"], "link": "https://www.cielotv.it/streaming.html"},
            "Nove": {"alias": ["nove", "nove hd"], "link": "https://www.nove.tv/"},
            "DMAX": {"alias": ["dmax", "dmax hd"], "link": "https://dmax.it/"},
            "SuperTennis": {"alias": ["supertennis", "super tennis", "supertennis hd"], "link": "https://www.supertennis.tv/"},
            "Sportitalia": {"alias": ["sportitalia", "sport italia", "sportitalia hd"], "link": "https://www.sportitalia.it/"},
            "SoloCalcio": {"alias": ["solocalcio", "solo calcio", "sportitalia solocalcio"], "link": "https://www.sportitalia.it/"},
        },
    },
    "Germania": {
        "epg_url": "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
        "canali": {
            "Das Erste": {"alias": ["das erste", "das erste hd", "ard"], "link": "https://www.ardmediathek.de/live"},
            "ZDF": {"alias": ["zdf", "zdf hd"], "link": "https://www.zdf.de/live-tv"},
            "RTL": {"alias": ["rtl", "rtl hd", "rtl television"], "link": "https://www.rtl.de/"},
            "Nitro": {"alias": ["nitro", "nitro hd", "rtl nitro"], "link": "https://www.rtl.de/"},
            "ProSieben": {"alias": ["prosieben", "prosieben hd", "pro7"], "link": "https://www.prosieben.de/"},
            "ProSieben MAXX": {"alias": ["prosieben maxx", "prosieben maxx hd", "pro7 maxx"], "link": "https://www.ran.de/"},
            "Sat.1": {"alias": ["sat.1", "sat 1", "sat1", "sat.1 hd"], "link": "https://www.ran.de/"},
            "Sport1": {"alias": ["sport1", "sport 1", "sport1 hd"], "link": "https://www.sport1.de/tv-programm"},
            "DF1": {"alias": ["df1", "df1 hd"], "link": "https://df1.de/"},
            "Eurosport 1 DE": {"alias": ["eurosport 1", "eurosport 1 hd", "eurosport1"], "link": "https://www.eurosport.de/"},
            "More Than Sports TV": {"alias": ["more than sports tv", "more than sports.tv"], "link": "https://morethansports.tv/"},
        },
    },
    "Svizzera": {
        "epg_url": "https://epgshare01.online/epgshare01/epg_ripper_CH1.xml.gz",
        "canali": {
            "RSI La 1": {"alias": ["rsi la 1", "rsi la1", "rsi la 1 hd"], "link": "https://www.rsi.ch/play/tv"},
            "RSI La 2": {"alias": ["rsi la 2", "rsi la2", "rsi la 2 hd"], "link": "https://www.rsi.ch/play/tv"},
            "SRF 1": {"alias": ["srf 1", "srf1", "srf 1 hd"], "link": "https://www.srf.ch/play/tv"},
            "SRF zwei": {"alias": ["srf zwei", "srf 2", "srf zwei hd"], "link": "https://www.srf.ch/play/tv"},
            "RTS 1": {"alias": ["rts 1", "rts un", "rts 1 hd"], "link": "https://www.rts.ch/play/tv"},
            "RTS 2": {"alias": ["rts 2", "rts deux", "rts 2 hd"], "link": "https://www.rts.ch/play/tv"},
            "blue Zoom": {"alias": ["blue zoom", "blue zoom d", "blue zoom f"], "link": "https://www.blueplus.ch/de/bluezoom"},
        },
    },
}

CANALI_BR_INFO = [
    ("CazéTV (YouTube)", "https://www.youtube.com/@CazeTV", [r"\bcaz[ée]tv\b"]),
    ("GE TV (YouTube)", "https://www.youtube.com/@getv", [r"\bge\s*tv\b"]),
    ("Canal GOAT (YouTube)", "https://www.youtube.com/@canalgoatbr", [r"\bcanal\s*goat\b"]),
    ("Xsports (YouTube)", "https://www.youtube.com/@xsports.brasil", [r"\bx\s*sports\b"]),
    ("SportyNet (YouTube)", "https://www.youtube.com/@SportyNetBrasil", [r"\bsportynet\b"]),
    ("N Sports (YouTube)", "https://www.youtube.com/@NSports", [r"\bn\s*sports\b"]),
    ("Romário TV (YouTube)", "https://www.youtube.com/@RomarioTVoficial", [r"\brom[áa]rio\s*tv\b", r"\btv\s*rom[áa]rio\b"]),
    ("Time Brasil (YouTube)", "https://www.youtube.com/@TimeBrasil", [r"\btime\s*brasil\b"]),
    ("NBA Brasil (YouTube)", "https://www.youtube.com/@nbabrasil", [r"\bnba\s*brasil\b"]),
    ("NBB (YouTube)", "https://www.youtube.com/@NBB", [r"youtube\s*\(nbb\)", r"nbb\s*\(youtube\)"]),
    ("SBT Sports (YouTube)", "https://www.youtube.com/@SBTSports", [r"\bsbt\s*sports\b", r"youtube.*\bsbt\b"]),
    ("CNN Esportes (YouTube)", "https://www.youtube.com/@cnnesportes", [r"\bcnn\s*esportes\b"]),
    ("Metrópoles Esportes (YouTube)", "https://www.youtube.com/@MetropolesEsportes", [r"\bmetr[óo]poles\s*esportes\b"]),
    ("Desimpedidos (YouTube)", "https://www.youtube.com/@desimpedidos", [r"\bdesimpedidos\b"]),
    ("TNT Sports (YouTube)", "https://www.youtube.com/@TNTSportsBR", [r"tnt\s*sports.*youtube", r"youtube.*tnt\s*sports"]),
    ("ESPN Brasil (YouTube)", "https://www.youtube.com/@espnbrasil", [r"espn.*youtube", r"youtube.*espn"]),
    ("Canal GOL Brasil (YouTube)", "https://www.youtube.com/@canalgolbrasil", [r"canal\s*gol\s*br", r"golbrasil\s*youtube"]),
    ("Jovem Pan Esportes (YouTube)", "https://www.youtube.com/@jovempanesportes", [r"\bjovem\s*pan\b.*youtube", r"youtube.*\bjovem\s*pan\b", r"\bjovem\s*pan\s*esportes\b"]),
    ("Vôlei Brasil / CBV (YouTube)", "https://www.youtube.com/@voleibrasil", [r"v[ôo]lei\s*brasil", r"canal\s*v[ôo]lei"]),
    ("LNF / CBFS Futsal (YouTube)", "https://www.youtube.com/@LNFTV", [r"\blnf\s*(?:tv|\(youtube\))", r"\bcbfs\s*tv\b"]),
    ("CONCACAF (YouTube)", "https://www.youtube.com/@concacaf", [r"concacaf.*youtube", r"youtube.*concacaf"]),
    ("A-Leagues (YouTube)", "https://www.youtube.com/@aleagues", [r"a-leagues.*youtube", r"youtube.*a-leagues"]),
]

PAROLE_DA_ESCLUDERE = [
    "telegiornale", "tg1", "tg2", "tg3", "tagesschau", "heute-journal",
    "meteo", "previsioni", "teleshopping",
]

REPLAY_REGEX = (
    r"\(\s*r\s*\)|\[\s*r\s*\]|"
    r"\b(?:replic[ah]e?|in\s+replica|differita|in\s+differita|"
    r"wiederholung|wdh\.?|rediffusion|rediff\.?|en\s+reprise|"
    r"repetici[óo]n|diferido|replay|re-?run|tape\s+delay|"
    r"partita\s+storica|partite\s+storiche|match\s+storico|archivio|amarcord|vintage|rewind|throwback)\b"
)

ESCLUDI_SPORT_REGEX = [
    r"\bcurling\b",
    r"\b(?:equitazione|ippica|horse racing|h[íi]pica|equestrian|pferdesport|pferderennen|reitsport|springreiten|dressur|galopp|show jumping|salto ostacoli)\b",
    r"\bp[áa]del\b",
    r"\b(?:scacchi|chess|ajedrez|schach|xadrez|[ée]checs)\b",
]

SECONDA_DIVISIONE_REGEX = (
    r"\b(?:"
    r"serie\s*a2|lvf\s*a2|a2\s*(?:credem|maschile|femminile|\(m\)|\(f\))|"
    r"serie\s*a3|2\.?\s*bundesliga|zweite\s*bundesliga|3\.?\s*liga|dritte\s*liga|"
    r"segunda\s*divisi[óo]n|laliga\s*hypermotion|laliga\s*2|la\s*liga\s*2|primera\s*federaci[óo]n|"
    r"ligue\s*2|ligue\s*b|efl\s*championship|league\s*one|league\s*two|"
    r"challenge\s*league|challenger\s*pro\s*league|1b\s*pro\s*league|"
    r"eerste\s*divisie|keuken\s*kampioen|liga\s*portugal\s*2|segunda\s*liga|"
    r"superliga\s*b|superliga\s*2|proa|prob|lnb\s*pro\s*b|2\.\s*basketball|"
    r"leb\s*oro|primera\s*feb|segunda\s*feb|"
    r"g[\s-]*league|del2|swiss\s*league|j2\s*league|j3\s*league|j2|j3|"
    r"s[ée]rie\s*[cd]|serie\s*[cd]|série\s*b|"
    r"seconda\s*divisione|second\s*division|2a\s*divisione|2nd\s*division|divisi[óo]n\s*de\s*plata|"
    r"brasileir[ãa]o\s*(?:s[ée]rie\s*)?b|paulist[ãa]o\s*a2|paulista\s*a2"
    r")\b"
)

MAGAZINE_IT_REGEX = (
    r"\b(?:"
    r"magazine|rubrica|rotocalco|approfondimento|talk\s*show|"
    r"domenica\s+sportiva|90[°º]?\s*minuto|novantesimo\s+minuto|pressing|dribbling|"
    r"tutti\s+convocati|fantacalcio|calciomercato|calcio\s*mercato|sportitalia\s+(?:mercato|live)|"
    r"sport\s*mediaset|sportmediaset|tg\s*sport|studio\s*sport|processo\s+del\s+luned[ìi]|"
    r"moviola|anteprima|prepartita|pre-?partita|postpartita|post-?partita|pre-?gara|post-?gara|"
    r"paddock|griglia\s+di\s+partenza|highlights|sintesi|i\s+gol\s+del|tutti\s+i\s+gol|zona\s+gol|"
    r"fuorigioco|tiki\s*taka|contropiede|supertennis\s+(?:magazine|today)|tennis\s+talk|"
    r"speciale\s+(?:calcio|sport|serie|moto|f1|formula|volley|basket|tennis)"
    r")\b"
)

MAGAZINE_ESTERI_REGEX = (
    r"\b(?:"
    r"magazin[es]?|rubrica|approfondimento|talk\s*show|podcast|cortes|resenha|mesa\s+redonda|debate|"
    r"sportschau|sportstudio|doppelpass|fantalk|sky90|bundesliga\s+pur|heimspiel|blickpunkt\s+sport|"
    r"sportpanorama|sportflash|sportaktuell|domenica\s+sportiva|"
    r"zusammenfassung|r[üu]ckblick|vorschau|vorbericht|countdown|dokumentation|doku|reportage|"
    r"[ée]mission|r[ée]sum[ée]|temps\s+forts|r[ée]trospective|avant-?match|apr[èe]s-?match|d[ée]brief|documentaire|"
    r"highlights|preview|review|watchalong|trending|rueda\s+de\s+prensa|press\s+conference|pesaje|weigh-?in|"
    r"documentary|docuseries|all\s+access|behind\s+the\s+scenes|paddock\s+abierto"
    r")\b"
)

CALCIO_FEMMINILE_REGEX = r"\b(?:femminil[ei]|feminino|feminina|femenin[ao]|f[ée]minin[eo]?|frauen|damen|women'?s?|woman|liga f|uwcl|wsl|nwsl|d1 arkema|frauenfu[ßs]ball)\b"

REGOLE_SPORT = [
    ("College Football", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b"]),
    ("Football Americano", [r"\bnfl\b", r"\bfoot us\b", r"\bfutebol americano\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bfútbol americano\b", r"\bsuper bowl\b", r"\bran football\b", r"\bflag football\b", r"redzone", r"アメフト"]),
    ("Formula 1", [r"\bformula 1\b", r"\bf[óo]rmula 1\b", r"\bformula uno\b", r"\bformel 1\b", r"\bformule 1\b", r"\bf1\b", r"\bgran premio di f1\b", r"\bgarage f1\b"]),
    ("MotoGP", [r"\bmotogp\b", r"\bmoto gp\b", r"\bmoto2\b", r"\bmoto3\b", r"\bmotomondiale\b", r"\bsuperbike\b", r"\bwsbk\b"]),
    ("Sci Alpino", [r"\bsci alpino\b", r"\bski alpin\b", r"\bski weltcup\b", r"\bski-weltcup\b", r"\bslalom\b", r"\bdiscesa libera\b", r"\bsuper-g\b", r"\bsuper g\b", r"\briesenslalom\b", r"\babfahrt\b", r"\bcoppa del mondo di sci\b"]),
    ("Pallavolo", [r"\bpallavolo\b", r"\bvolley\b", r"\bvolleyball\b", r"\bv[ôo]lei\b", r"\bsuperlega\b", r"\bsuperliga\b", r"\blvf\b", r"\bvnl\b", r"\bserie a1\b", r"バレー"]),
    ("Basket & NBA", [r"\bnba\b", r"\bwnba\b", r"\bbasket\b", r"\bbasquete\b", r"\bbaloncesto\b", r"\bpallacanestro\b", r"\bbasketball\b", r"\beurolega\b", r"\beuroleague\b", r"\beurocup\b", r"\beuroliga\b", r"\bnbb\b", r"\bfiba\b", r"\blega basket\b", r"\bliga endesa\b", r"\bliga acb\b", r"\bliga betclic\b", r"\bmarch madness\b", r"\bbbl\b", r"バスケ", r"bリーグ"]),
    ("Tennis", [r"\btennis\b", r"\bt[êe]nis\b", r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bcoppa davis\b", r"\bdavis cup\b", r"\bbillie jean king\b", r"\broland garros\b", r"\bwimbledon\b", r"\baustralian open\b", r"\bus open\b", r"\bchallenger\b", r"テニス"]),
    ("Calcio", [r"\bcalcio\b", r"\bfutebol\b", r"\bf[úu]tbol\b", r"\bfootball\b", r"\bsoccer\b", r"\bfu[ßs]ball\b", r"\bvoetbal\b", r"\bserie a\b", r"\bserie b(?:kt)?\b", r"\bcoppa italia\b", r"\bsupercoppa\b", r"\bchampions league\b", r"\beuropa league\b", r"\bconference league\b", r"\bnations league\b", r"\bmondiali\b", r"\bpremier league\b", r"\bbundesliga\b", r"\bdfb-pokal\b", r"\bdfb pokal\b", r"\blaliga\b", r"\bla liga\b", r"\bligue 1\b", r"\bbrasileir[ãa]o\b", r"\bpaulist[ãa]o\b", r"\bcarioca\b", r"\bcopa do brasil\b", r"\blibertadores\b", r"\bsul-americana\b", r"\bsudamericana\b", r"\bsuper league\b", r"\bjupiler\b", r"\bcroky cup\b", r"\bliga portugal\b", r"\bfa cup\b", r"\bcopa del rey\b", r"\bfutsal\b", r"\bfifa\b", r"\bkings league\b", r"\byouth league\b", r"\bu17-wm\b", r"\bu-17\b", r"\bjリーグ\b", r"\bj1\b", r"サッカー", r"セリエa", r"ラリーガ", r"ブンデスリーガ", r"リーグアン", r"ベルギーリーグ"]),
]


def classifica_sport(testo, canale_solo_sport=False, paese="", title=""):
    t = (testo or "").lower()
    tl = (title or testo or "").lower()

    if any(p in t for p in PAROLE_DA_ESCLUDERE):
        return None
    if re.search(REPLAY_REGEX, tl):
        return None
    if re.search(REPLAY_REGEX, t) and not re.search(r"\b(?:diretta|live)\b", tl):
        return None
    if any(re.search(pat, t) for pat in ESCLUDI_SPORT_REGEX):
        return None
    if re.search(SECONDA_DIVISIONE_REGEX, t):
        return None

    is_match_or_race = bool(
        re.search(r"(\s+-\s+|\bvs\.?\b|×|\s+x\s+|\s+@\s+|\b(?:gran premio|grand prix|qualifiche|qualifying|gara|race|sprint|slalom|discesa|super-?g|gigante|semifinale|finale|quarti|ottavi)\b)", tl)
    )

    if paese == "Italia":
        if re.search(MAGAZINE_IT_REGEX, tl) or (not is_match_or_race and re.search(MAGAZINE_IT_REGEX, t)):
            return "Programmi & Magazine"
    else:
        if re.search(MAGAZINE_ESTERI_REGEX, tl) or (not is_match_or_race and re.search(MAGAZINE_ESTERI_REGEX, t)):
            return None

    for sport, patterns in REGOLE_SPORT:
        if any(re.search(pat, t) for pat in patterns):
            if sport == "Calcio":
                if re.search(CALCIO_FEMMINILE_REGEX, t):
                    return None
                if re.search(r"\bserie\s*b(?:kt)?\b", t):
                    if paese not in ("Italia", "DAZN Free Italia", "") or re.search(r"\b(?:brasil|brasileir|argentin|ecuador|colombia|chile|rugby|basket|volley|pallavolo)\b", t):
                        return None
            else:
                if re.search(r"\bserie\s*b(?:kt)?\b", t):
                    return None
            return sport

    if canale_solo_sport and re.search(r"(\bx\b|vs\.?|×|対|\s-\s|\s·\s|\s@\s)", t):
        if re.search(r"\bserie\s*b(?:kt)?\b", t):
            return None
        return "Altri Sport"
    return None


def scarica_epg_paesi():
    risultati = []
    for paese, cfg in PAESI_TV.items():
        alias_map = {re.sub(r"\s+", " ", al.strip().lower()): (n, info["link"]) for n, info in cfg["canali"].items() for al in info["alias"]}
        print(f"📡 Scarico guida TV per {paese}...")
        try:
            resp = requests.get(cfg["epg_url"], timeout=90, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            print(f"⚠️ Errore EPG {paese}: {e}")
            continue
        matched_ids, count = {}, 0
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as gz:
                for _, elem in ET.iterparse(gz, events=("end",)):
                    if elem.tag == "channel":
                        cid = elem.attrib.get("id", "")
                        for dn in elem.findall("display-name"):
                            k = re.sub(r"\s+", " ", (dn.text or "").strip().lower())
                            if k in alias_map:
                                matched_ids[cid] = alias_map[k]
                                break
                        elem.clear()
                    elif elem.tag == "programme":
                        cid = elem.attrib.get("channel", "")
                        if cid in matched_ids:
                            s = (elem.attrib.get("start") or "").strip()
                            if s and " " not in s:
                                s = s[:14] + " +0000"
                            try:
                                dt = datetime.strptime(s, "%Y%m%d%H%M%S %z").astimezone(ROME_TZ)
                            except Exception:
                                dt = None
                            if dt and MIN_DT <= dt <= MAX_DT:
                                title = (elem.findtext("title") or "").strip()
                                desc = (elem.findtext("desc") or "").strip()
                                cats = " ".join((c.text or "") for c in elem.findall("category"))
                                sport = classifica_sport(f"{title} {cats} {desc}", False, paese=paese, title=f"{title} {cats}")
                                if sport and title:
                                    nc, lk = matched_ids[cid]
                                    comp_lbl = "Programma TV" if sport == "Programmi & Magazine" else (cats.strip() or f"TV {paese}")
                                    risultati.append({"data": dt.strftime("%Y-%m-%d"), "ora": dt.strftime("%H:%M"), "sport": sport, "competizione": comp_lbl, "evento": title, "paese": paese, "canale": nc, "link": lk})
                                    count += 1
                        elem.clear()
        except Exception as e:
            print(f"⚠️ Errore XML {paese}: {e}")
        print(f"✅ {paese}: trovati {count} eventi")
    return risultati


def risolvi_canali_br(testo):
    t = (testo or "").lower()
    trovati, visti = [], set()
    for nome, link, pats in CANALI_BR_INFO:
        if any(re.search(p, t) for p in pats) and nome not in visti:
            visti.add(nome)
            trovati.append((nome, link))
    if not trovati:
        for m in re.finditer(r"youtube\s*\(([^)]+)\)", testo or "", re.I):
            ex = m.group(1).strip()
            if ex and f"{ex} (YouTube)" not in visti:
                visti.add(f"{ex} (YouTube)")
                trovati.append((f"{ex} (YouTube)", f"https://www.youtube.com/results?search_query={quote_plus(ex)}"))
    return trovati


def scarica_futebol_tv_br():
    risultati, base = [], "https://futebol.tv.br"
    print("🇧🇷 Controllo futebol.tv.br/canais...")
    try:
        resp = requests.get(f"{base}/canais", headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception:
        return risultati
    soup = BeautifulSoup(resp.text, "html.parser")
    pagine = {}
    for a in soup.find_all("a", href=True):
        txt = re.sub(r"\d+\s*pr[óo]ximos?\s*jogos.*", "", a.get_text(" ", strip=True), flags=re.I).strip()
        mc = risolvi_canali_br(txt)
        if mc:
            u = urljoin(base, a["href"])
            if u not in pagine:
                pagine[u] = mc[0]
    for url_p, (nc, lyt) in pagine.items():
        try:
            r = requests.get(url_p, headers=HEADERS, timeout=25)
            r.raise_for_status()
        except Exception:
            continue
        testo = BeautifulSoup(r.text, "html.parser").get_text("\n")
        testo = testo.split("Próximos jogos", 1)[-1].split("Histórico recente", 1)[0]
        cd = ct = None
        for rl in testo.splitlines():
            line = re.sub(r"\s+", " ", rl).strip()
            if not line:
                continue
            md = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", line)
            if md:
                cd = md.group(1)
                continue
            mt = re.search(r"\b(\d{2}:\d{2})\b", line)
            if mt and len(line) < 25:
                ct = mt.group(1)
                continue
            if cd and ct and " x " in line and "Ver jogo" not in line and "Logo " not in line:
                parti = [p.strip() for p in line.split("·") if p.strip()]
                ev = parti[0]
                comp = re.sub(r"Logo\s+.*", "", parti[1] if len(parti) > 1 else "Calcio").strip() or "Calcio"
                if classifica_sport(f"futebol {comp} {ev}", True, paese="Brasile YouTube", title=f"{comp} {ev}") != "Calcio":
                    ct = None
                    continue
                try:
                    dt_it = datetime.strptime(f"{cd} {ct}", "%d/%m/%Y %H:%M").replace(tzinfo=BR_TZ).astimezone(ROME_TZ)
                    if MIN_DT <= dt_it <= MAX_DT:
                        risultati.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": "Calcio", "competizione": comp, "evento": ev, "paese": "Brasile YouTube", "canale": nc, "link": lyt})
                except Exception:
                    pass
                ct = None
    print(f"✅ futebol.tv.br: {len(risultati)} eventi")
    return risultati


def risolvi_data_post_br(pub_dt, title_text):
    m = re.search(r"\((\d{1,2})(?:/\d{1,2})?\)", title_text or "") or re.search(r"\b(\d{1,2})\s+de\s+[a-zç]+", (title_text or "").lower())
    if m:
        g = int(m.group(1))
        for d in (0, 1, -1):
            c = pub_dt + timedelta(days=d)
            if c.day == g:
                return c
    return pub_dt


def estrai_br_html(html, base_dt):
    ris, sez = [], ""
    for rl in BeautifulSoup(html, "html.parser").get_text("\n").splitlines():
        line = re.sub(r"\s+", " ", rl).strip()
        if not line:
            continue
        if len(line) < 55 and not re.match(r"^\d{1,2}h", line):
            if any(k in line.lower() for k in ["futebol", "vôlei", "volei", "basquete", "nba", "nbb", "futsal", "tênis", "automobilismo", "fórmula 1", "motogp", "nfl", "brasileirão", "laliga", "bundesliga", "premier league", "ligue 1"]):
                sez = line
            continue
        m = re.match(r"^(\d{1,2})h(\d{2})?\s*[–—\-]\s*(.+?)\s+[–—\-]\s+(.+)$", line)
        if not m:
            continue
        cf = risolvi_canali_br(m.group(4))
        if not cf:
            continue
        corpo = m.group(3).strip()
        comp, ev = ([x.strip() for x in corpo.split(":", 1)] if ":" in corpo else (sez or "Sport Brasile", corpo))
        sport = classifica_sport(f"{sez} {comp} {ev}", True, paese="Brasile YouTube", title=f"{comp} {ev}")
        if not sport:
            continue
        try:
            dt_it = datetime(base_dt.year, base_dt.month, base_dt.day, int(m.group(1)), int(m.group(2) or "0"), tzinfo=BR_TZ).astimezone(ROME_TZ)
        except Exception:
            continue
        if MIN_DT <= dt_it <= MAX_DT:
            nome = " / ".join(c[0].replace(" (YouTube)", "") for c in cf) + " (YouTube)"
            ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": sport, "competizione": comp, "evento": ev, "paese": "Brasile YouTube", "canale": nome, "link": cf[0][1]})
    return ris


def scarica_auvaromaia_br():
    ris = []
    try:
        r = requests.get("https://auvaromaia.com/wp-json/wp/v2/posts?search=Agenda+esportiva&per_page=7", headers=HEADERS, timeout=25)
        r.raise_for_status()
        for p in r.json():
            tit = BeautifulSoup(p.get("title", {}).get("rendered", ""), "html.parser").get_text()
            if "agenda esportiva" in tit.lower():
                ris.extend(estrai_br_html(p.get("content", {}).get("rendered", ""), risolvi_data_post_br(datetime.fromisoformat(p["date"][:19]), tit)))
    except Exception:
        try:
            r = requests.get("https://auvaromaia.com/feed/", headers=HEADERS, timeout=25)
            root = ET.fromstring(r.text)
            ns = {"c": "http://purl.org/rss/1.0/modules/content/"}
            for it in root.findall("./channel/item"):
                tit = it.findtext("title") or ""
                if "agenda esportiva" in tit.lower():
                    try:
                        pdt = parsedate_to_datetime(it.findtext("pubDate") or "").replace(tzinfo=None)
                    except Exception:
                        pdt = NOW
                    ris.extend(estrai_br_html(it.findtext("c:encoded", namespaces=ns) or it.findtext("description") or "", risolvi_data_post_br(pdt, tit)))
        except Exception:
            pass
    print(f"✅ AuvaroMaia: {len(ris)} eventi")
    return ris


def scarica_gfesporte_br():
    ris = []
    try:
        r = requests.get("https://www.gfesporte.com.br/", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, "html.parser")
        links, visti = [], set()
        for a in soup.find_all("a", href=True):
            href, txt = urljoin("https://www.gfesporte.com.br/", a["href"]), a.get_text(" ", strip=True)
            if ("programacao-esportiva" in href.lower() or "agenda esportiva" in txt.lower() or "programação esportiva" in txt.lower()) and href not in visti:
                visti.add(href)
                links.append((href, txt))
        for u, txt in links[:5]:
            rp = requests.get(u, headers=HEADERS, timeout=25)
            h1 = BeautifulSoup(rp.text, "html.parser").find("h1")
            ris.extend(estrai_br_html(rp.text, risolvi_data_post_br(NOW.astimezone(BR_TZ), h1.get_text(" ", strip=True) if h1 else txt)))
    except Exception:
        pass
    print(f"✅ GFEsporte: {len(ris)} eventi")
    return ris


def carica_manuali():
    if not os.path.exists("eventi_manuali.json"):
        return []
    try:
        with open("eventi_manuali.json", "r", encoding="utf-8") as f:
            eventi = [ev for ev in json.load(f) if ev.get("data", "") >= NOW.strftime("%Y-%m-%d")]
            print(f"✍️ Eventi manuali caricati: {len(eventi)}")
            return eventi
    except Exception as e:
        print(f"⚠️ Errore lettura eventi_manuali.json: {e}")
        return []


def deduplica(eventi):
    visti, puliti = set(), []
    for ev in eventi:
        tb = re.sub(r"\b(fc|sc|ec|cr|ca)\b", "", ev.get("evento", "").split(":", 1)[-1].lower())
        k = (ev.get("data", ""), ev.get("ora", ""), ev.get("paese", ""), re.sub(r"[^a-z0-9]", "", tb)[:22])
        if k not in visti:
            visti.add(k)
            puliti.append(ev)
    puliti.sort(key=lambda x: (x.get("data", ""), x.get("ora", ""), x.get("paese", "")))
    return puliti


def main():
    tutti = (
        scarica_epg_paesi()
        + scarica_futebol_tv_br()
        + scarica_auvaromaia_br()
        + scarica_gfesporte_br()
        + carica_manuali()
    )
    finali = deduplica(tutti)
    if finali:
        with open("eventi.json", "w", encoding="utf-8") as f:
            json.dump(finali, f, ensure_ascii=False, indent=2)
        with open("meta.json", "w", encoding="utf-8") as f:
            json.dump({"ultimo_aggiornamento": NOW.strftime("%d/%m/%Y alle %H:%M"), "totale_eventi": len(finali)}, f, ensure_ascii=False, indent=2)
        print(f"🎉 Salvati {len(finali)} eventi totali in eventi.json!")


if __name__ == "__main__":
    main()
