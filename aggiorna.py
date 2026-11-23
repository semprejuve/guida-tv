import gzip
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except Exception:
    cffi_requests = None

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

ROME_TZ = ZoneInfo("Europe/Rome")
BR_TZ = ZoneInfo("America/Sao_Paulo")
NOW = datetime.now(ROME_TZ)
MIN_DT = NOW - timedelta(hours=2)
MAX_DT = NOW + timedelta(days=7)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,it;q=0.8,en;q=0.7",
}

# ==============================================================================
# 1) PAESI E CANALI TV GRATUITI (Europei / XMLTV)
# ==============================================================================
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

# ==============================================================================
# 2) CANALI YOUTUBE BRASILIANI GRATUITI
# ==============================================================================
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

# ==============================================================================
# 3) CLASSIFICATORE AUTOMATICO DEGLI SPORT
# ==============================================================================
PAROLE_DA_ESCLUDERE = [
    "telegiornale", "tg sport", "tg1", "tg2", "tg3", "sport mediaset",
    "sportmediaset", "tagesschau", "heute-journal", "meteo", "previsioni",
    "teleshopping", "rubrica", "cortes", "podcast", "resenha",
]

REGOLE_SPORT = [
    ("College Football", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b"]),
    ("Football Americano", [r"\bnfl\b", r"\bfoot us\b", r"\bfutebol americano\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bfútbol americano\b", r"\bsuper bowl\b", r"\bran football\b", r"アメフト"]),
    ("Formula 1", [r"\bformula 1\b", r"\bf[óo]rmula 1\b", r"\bformula uno\b", r"\bformel 1\b", r"\bformule 1\b", r"\bf1\b", r"\bgran premio di f1\b", r"\bgarage f1\b"]),
    ("MotoGP", [r"\bmotogp\b", r"\bmoto gp\b", r"\bmoto2\b", r"\bmoto3\b", r"\bmotomondiale\b", r"\bsuperbike\b", r"\bwsbk\b"]),
    ("Sci Alpino", [r"\bsci alpino\b", r"\bski alpin\b", r"\bski weltcup\b", r"\bski-weltcup\b", r"\bslalom\b", r"\bdiscesa libera\b", r"\bsuper-g\b", r"\bsuper g\b", r"\briesenslalom\b", r"\babfahrt\b", r"\bcoppa del mondo di sci\b"]),
    ("Pallavolo", [r"\bpallavolo\b", r"\bvolley\b", r"\bvolleyball\b", r"\bv[ôo]lei\b", r"\bsuperlega\b", r"\bsuperliga\b", r"\blvf\b", r"\bvnl\b", r"\bserie a1\b", r"\bserie a2\b", r"バレー"]),
    ("Basket & NBA", [r"\bnba\b", r"\bwnba\b", r"\bbasket\b", r"\bbasquete\b", r"\bbaloncesto\b", r"\bpallacanestro\b", r"\bbasketball\b", r"\beurolega\b", r"\beuroleague\b", r"\beurocup\b", r"\beuroliga\b", r"\bnbb\b", r"\bfiba\b", r"\blega basket\b", r"\bliga endesa\b", r"\bliga acb\b", r"\bliga betclic\b", r"\bmarch madness\b", r"\bbbl\b", r"バスケ", r"bリーグ"]),
    ("Tennis", [r"\btennis\b", r"\bt[êe]nis\b", r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bcoppa davis\b", r"\bdavis cup\b", r"\bbillie jean king\b", r"\broland garros\b", r"\bwimbledon\b", r"\baustralian open\b", r"\bus open\b", r"\bchallenger\b", r"テニス"]),
    ("Calcio", [
        r"\bcalcio\b", r"\bfutebol\b", r"\bf[úu]tbol\b", r"\bfootball\b", r"\bsoccer\b",
        r"\bfu[ßs]ball\b", r"\bvoetbal\b", r"\bserie a\b", r"\bserie b\b", r"\bs[ée]rie b\b",
        r"\bcoppa italia\b", r"\bsupercoppa\b", r"\bchampions league\b", r"\beuropa league\b",
        r"\bconference league\b", r"\bnations league\b", r"\bmondiali\b", r"\bpremier league\b",
        r"\bbundesliga\b", r"\bdfb-pokal\b", r"\bdfb pokal\b", r"\blaliga\b", r"\bla liga\b",
        r"\bligue 1\b", r"\bbrasileir[ãa]o\b", r"\bpaulist[ãa]o\b", r"\bcarioca\b",
        r"\bcopa do brasil\b", r"\blibertadores\b", r"\bsul-americana\b", r"\bsudamericana\b",
        r"\bsuper league\b", r"\bjupiler\b", r"\bchallenger pro league\b", r"\bcroky cup\b",
        r"\bliga f\b", r"\buwcl\b", r"\bfrauen-bundesliga\b", r"\bfrauen bundesliga\b",
        r"\bserie a women\b", r"\bserie a femminile\b", r"\bliga portugal\b", r"\bnational league\b",
        r"\bfa cup\b", r"\bcopa del rey\b", r"\bfutsal\b", r"\bfifa\b", r"\bkings league\b",
        r"\bjリーグ\b", r"\bj1\b", r"\bj2\b", r"\bj3\b", r"サッカー", r"セリエa", r"ラリーガ",
    ]),
]


def classifica_sport(testo, canale_solo_sport=False):
    t = (testo or "").lower()
    if any(p in t for p in PAROLE_DA_ESCLUDERE):
        return None
    for sport, patterns in REGOLE_SPORT:
        for pat in patterns:
            if re.search(pat, t):
                return sport
    if canale_solo_sport:
        if re.search(r"\b(x|vs\.?|@)\b", t) or " - " in t:
            return "Altri Sport"
    return None


def normalizza_nome_canale(nome):
    return re.sub(r"\s+", " ", (nome or "").strip().lower())


def parse_xmltv_date(s):
    if not s:
        return None
    s = s.strip()
    if " " not in s:
        s = s[:14] + " +0000"
    try:
        return datetime.strptime(s, "%Y%m%d%H%M%S %z").astimezone(ROME_TZ)
    except Exception:
        return None


def scarica_epg_paesi():
    risultati = []
    for paese, cfg in PAESI_TV.items():
        url = cfg["epg_url"]
        alias_map = {}
        for nome_ufficiale, info in cfg["canali"].items():
            for al in info["alias"]:
                alias_map[normalizza_nome_canale(al)] = (nome_ufficiale, info["link"])

        print(f"📡 Scarico guida TV per {paese}...")
        try:
            resp = requests.get(url, timeout=90, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            print(f"⚠️ Impossibile scaricare EPG {paese}: {e}")
            continue

        matched_ids = {}
        count_paese = 0
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as gz:
                for _, elem in ET.iterparse(gz, events=("end",)):
                    if elem.tag == "channel":
                        cid = elem.attrib.get("id", "")
                        for dn in elem.findall("display-name"):
                            norm = normalizza_nome_canale(dn.text)
                            if norm in alias_map:
                                matched_ids[cid] = alias_map[norm]
                                break
                        elem.clear()
                    elif elem.tag == "programme":
                        cid = elem.attrib.get("channel", "")
                        if cid in matched_ids:
                            dt = parse_xmltv_date(elem.attrib.get("start"))
                            if dt and MIN_DT <= dt <= MAX_DT:
                                title = (elem.findtext("title") or "").strip()
                                desc = (elem.findtext("desc") or "").strip()
                                cats = " ".join((c.text or "") for c in elem.findall("category"))
                                sport = classifica_sport(f"{title} {cats} {desc}", canale_solo_sport=False)
                                if sport and title:
                                    nome_canale, link_canale = matched_ids[cid]
                                    risultati.append({
                                        "data": dt.strftime("%Y-%m-%d"),
                                        "ora": dt.strftime("%H:%M"),
                                        "sport": sport,
                                        "competizione": cats.strip() or f"TV {paese}",
                                        "evento": title,
                                        "paese": paese,
                                        "canale": nome_canale,
                                        "link": link_canale,
                                    })
                                    count_paese += 1
                        elem.clear()
        except Exception as e:
            print(f"⚠️ Errore lettura XML {paese}: {e}")
        print(f"✅ {paese}: trovati {count_paese} eventi sportivi")
    return risultati


# ==============================================================================
# CANALI YOUTUBE BRASILIANI (3 SORGENTI)
# ==============================================================================
def risolvi_canali_br(testo_canali):
    t = (testo_canali or "").lower()
    trovati = []
    visti = set()
    for nome_uff, link, patterns in CANALI_BR_INFO:
        if any(re.search(pat, t) for pat in patterns):
            if nome_uff not in visti:
                visti.add(nome_uff)
                trovati.append((nome_uff, link))

    if not trovati:
        for m in re.finditer(r"youtube\s*\(([^)]+)\)", testo_canali or "", re.IGNORECASE):
            nome_extra = m.group(1).strip()
            if nome_extra:
                label = f"{nome_extra} (YouTube)"
                if label not in visti:
                    visti.add(label)
                    trovati.append((label, f"https://www.youtube.com/results?search_query={quote_plus(nome_extra)}"))
    return trovati


def scarica_futebol_tv_br():
    risultati = []
    base_url = "https://futebol.tv.br"
    print("🇧🇷 Controllo futebol.tv.br/canais (programmazione settimanale YouTube BR)...")
    try:
        resp = requests.get(f"{base_url}/canais", headers=BROWSER_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️ futebol.tv.br non raggiungibile: {e}")
        return risultati

    soup = BeautifulSoup(resp.text, "html.parser")
    pagine_canali = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        testo_link = re.sub(r"\d+\s*pr[óo]ximos?\s*jogos.*", "", a.get_text(" ", strip=True), flags=re.IGNORECASE).strip()
        if not testo_link:
            continue
        match_canali = risolvi_canali_br(testo_link)
        if match_canali:
            full_url = urljoin(base_url, href)
            nome_uff, link_yt = match_canali[0]
            if full_url not in pagine_canali:
                pagine_canali[full_url] = (nome_uff, link_yt)

    for page_url, (nome_canale, link_yt) in pagine_canali.items():
        try:
            r = requests.get(page_url, headers=BROWSER_HEADERS, timeout=25)
            r.raise_for_status()
        except Exception:
            continue

        psoup = BeautifulSoup(r.text, "html.parser")
        testo = psoup.get_text("\n")
        if "Próximos jogos" in testo:
            testo = testo.split("Próximos jogos", 1)[1]
        if "Histórico recente" in testo:
            testo = testo.split("Histórico recente", 1)[0]

        current_date = None
        current_time = None
        for raw_line in testo.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue

            m_date = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", line)
            if m_date:
                current_date = m_date.group(1)
                continue

            m_time = re.search(r"\b(\d{2}:\d{2})\b", line)
            if m_time and len(line) < 25:
                current_time = m_time.group(1)
                continue

            if current_date and current_time and " x " in line and "Ver jogo" not in line and "Logo " not in line:
                parti = [p.strip() for p in line.split("·") if p.strip()]
                evento = parti[0]
                competizione = parti[1] if len(parti) > 1 else "Calcio Brasile / Mondo"
                competizione = re.sub(r"Logo\s+.*", "", competizione).strip() or "Calcio"
                try:
                    dt_br = datetime.strptime(f"{current_date} {current_time}", "%d/%m/%Y %H:%M").replace(tzinfo=BR_TZ)
                    dt_it = dt_br.astimezone(ROME_TZ)
                    if MIN_DT <= dt_it <= MAX_DT:
                        risultati.append({
                            "data": dt_it.strftime("%Y-%m-%d"),
                            "ora": dt_it.strftime("%H:%M"),
                            "sport": "Calcio",
                            "competizione": competizione,
                            "evento": evento,
                            "paese": "Brasile YouTube",
                            "canale": nome_canale,
                            "link": link_yt,
                        })
                except Exception:
                    pass
                current_time = None

    print(f"✅ futebol.tv.br: trovati {len(risultati)} eventi YouTube BR")
    return risultati


def risolvi_data_post_br(pub_dt, title_text):
    m = re.search(r"\((\d{1,2})(?:/\d{1,2})?\)
