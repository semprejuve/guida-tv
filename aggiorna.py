import gzip
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse
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

try:
    from googlenewsdecoder import gnewsdecoder as _gnews_fn
except Exception:
    try:
        from googlenewsdecoder import new_decoderv1 as _gnews_fn
    except Exception:
        _gnews_fn = None

ROME_TZ = ZoneInfo("Europe/Rome")
BR_TZ = ZoneInfo("America/Sao_Paulo")
JP_TZ = ZoneInfo("Asia/Tokyo")
NOW = datetime.now(ROME_TZ)
MIN_DT = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
MAX_DT = NOW + timedelta(days=7)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
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
    ("Football Americano", [r"\bnfl\b", r"\bfoot us\b", r"\bfutebol americano\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bfútbol americano\b", r"\bsuper bowl\b", r"\bran football\b", r"\bflag football\b", r"redzone", r"アメフト"]),
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
        r"\byouth league\b", r"\bu17-wm\b", r"\bu-17\b", r"\bjリーグ\b", r"\bj1\b", r"\bj2\b", r"\bj3\b",
        r"サッカー", r"セリエa", r"ラリーガ", r"ブンデスリーガ", r"リーグアン", r"ベルギーリーグ",
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
    if canale_solo_sport and (re.search(r"\b(x|vs\.?|@)\b", t) or " - " in t or " · " in t):
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
    m = re.search(r"\((\d{1,2})(?:/\d{1,2})?\)", title_text or "")
    if not m:
        m = re.search(r"\b(\d{1,2})\s+de\s+[a-zç]+", (title_text or "").lower())
    if m:
        giorno = int(m.group(1))
        for delta in (0, 1, -1):
            cand = pub_dt + timedelta(days=delta)
            if cand.day == giorno:
                return cand
    return pub_dt


def estrai_eventi_da_html_br(html_content, base_date_br):
    risultati = []
    soup = BeautifulSoup(html_content, "html.parser")
    sezione = ""

    for raw_line in soup.get_text("\n").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        if len(line) < 55 and not re.match(r"^\d{1,2}h", line):
            low = line.lower()
            if any(k in low for k in [
                "futebol", "vôlei", "volei", "basquete", "nba", "nbb", "futsal",
                "tênis", "tenis", "automobilismo", "fórmula 1", "formula 1",
                "motogp", "nfl", "brasileirão", "laliga", "bundesliga",
                "premier league", "ligue 1", "sul-americana", "libertadores",
            ]):
                sezione = line
            continue

        m = re.match(r"^(\d{1,2})h(\d{2})?\s*[–—\-]\s*(.+?)\s+[–—\-]\s+(.+)$", line)
        if not m:
            continue

        hh = int(m.group(1))
        mm = int(m.group(2) or "0")
        corpo = m.group(3).strip()
        canali_str = m.group(4).strip()

        canali_trovati = risolvi_canali_br(canali_str)
        if not canali_trovati:
            continue

        if ":" in corpo:
            comp, evento = [x.strip() for x in corpo.split(":", 1)]
        else:
            comp = sezione or "Sport Brasile"
            evento = corpo

        sport = classifica_sport(f"{sezione} {comp} {evento}", canale_solo_sport=True)
        if not sport:
            continue

        try:
            dt_br = datetime(base_date_br.year, base_date_br.month, base_date_br.day, hh, mm, tzinfo=BR_TZ)
            dt_it = dt_br.astimezone(ROME_TZ)
        except Exception:
            continue

        if not (MIN_DT <= dt_it <= MAX_DT):
            continue

        nomi_puliti = [c[0].replace(" (YouTube)", "") for c in canali_trovati]
        nome_finale = " / ".join(nomi_puliti) + " (YouTube)"
        link_finale = canali_trovati[0][1]

        risultati.append({
            "data": dt_it.strftime("%Y-%m-%d"),
            "ora": dt_it.strftime("%H:%M"),
            "sport": sport,
            "competizione": comp,
            "evento": evento,
            "paese": "Brasile YouTube",
            "canale": nome_finale,
            "link": link_finale,
        })
    return risultati


def scarica_auvaromaia_br():
    risultati = []
    print("🇧🇷 Controllo AuvaroMaia (tutti gli sport BR)...")
    try:
        r = requests.get(
            "https://auvaromaia.com/wp-json/wp/v2/posts?search=Agenda+esportiva&per_page=7",
            headers=BROWSER_HEADERS,
            timeout=25,
        )
        r.raise_for_status()
        for post in r.json():
            titolo = BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text()
            if "agenda esportiva" not in titolo.lower():
                continue
            pub_dt = datetime.fromisoformat(post["date"][:19])
            base_dt = risolvi_data_post_br(pub_dt, titolo)
            risultati.extend(estrai_eventi_da_html_br(post.get("content", {}).get("rendered", ""), base_dt))
    except Exception as e:
        print(f"⚠️ API AuvaroMaia saltata ({e}), provo RSS...")
        try:
            r = requests.get("https://auvaromaia.com/feed/", headers=BROWSER_HEADERS, timeout=25)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
            for item in root.findall("./channel/item"):
                titolo = item.findtext("title") or ""
                if "agenda esportiva" not in titolo.lower():
                    continue
                pub_str = item.findtext("pubDate") or ""
                try:
                    pub_dt = datetime.strptime(pub_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                except Exception:
                    pub_dt = NOW
                base_dt = risolvi_data_post_br(pub_dt, titolo)
                html = item.findtext("content:encoded", namespaces=ns) or item.findtext("description") or ""
                risultati.extend(estrai_eventi_da_html_br(html, base_dt))
        except Exception as e2:
            print(f"⚠️ Anche RSS AuvaroMaia saltato: {e2}")
    print(f"✅ AuvaroMaia: trovati {len(risultati)} eventi YouTube BR")
    return risultati


def scarica_gfesporte_br():
    risultati = []
    print("🇧🇷 Controllo GFEsporte (Backup tutti gli sport BR)...")
    try:
        r = requests.get("https://www.gfesporte.com.br/", headers=BROWSER_HEADERS, timeout=25)
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ GFEsporte non raggiungibile: {e}")
        return risultati

    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    visti = set()
    for a in soup.find_all("a", href=True):
        href = urljoin("https://www.gfesporte.com.br/", a["href"])
        txt = a.get_text(" ", strip=True)
        if ("programacao-esportiva" in href.lower() or "agenda esportiva" in txt.lower() or "programação esportiva" in txt.lower()) and href not in visti:
            visti.add(href)
            links.append((href, txt))

    for url_post, txt in links[:5]:
        try:
            rp = requests.get(url_post, headers=BROWSER_HEADERS, timeout=25)
            rp.raise_for_status()
            psoup = BeautifulSoup(rp.text, "html.parser")
            titolo = (psoup.find("h1").get_text(" ", strip=True) if psoup.find("h1") else txt)
            base_dt = risolvi_data_post_br(NOW.astimezone(BR_TZ), titolo)
            risultati.extend(estrai_eventi_da_html_br(rp.text, base_dt))
        except Exception:
            continue
    print(f"✅ GFEsporte: trovati {len(risultati)} eventi YouTube BR")
    return risultati


# ==============================================================================
# 4) DAZN FREE ITALIA & ESTERO (IT, BE, DE, CA, JP, ES, PT)
# ==============================================================================
MESI_MAP = {
    "gennaio": 1, "gen": 1, "febbraio": 2, "feb": 2, "marzo": 3, "mar": 3,
    "aprile": 4, "apr": 4, "maggio": 5, "mag": 5, "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7, "agosto": 8, "ago": 8, "settembre": 9, "set": 9,
    "ottobre": 10, "ott": 10, "novembre": 11, "nov": 11, "dicembre": 12, "dic": 12,
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "mai": 5, "juni": 6,
    "juli": 7, "oktober": 10, "dezember": 12,
    "janvier": 1, "janv": 1, "février": 2, "fevrier": 2, "févr": 2, "mars": 3,
    "avril": 4, "avr": 4, "juin": 6, "juillet": 7, "juil": 7, "août": 8,
    "aout": 8, "septembre": 9, "sept": 9, "octobre": 10, "décembre": 12, "decembre": 12,
    "januari": 1, "februari": 2, "maart": 3, "mei": 5, "augustus": 8, "december": 12,
    "enero": 1, "febrero": 2, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "maio": 5, "junho": 6,
    "julho": 7, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "january": 1, "jan": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "october": 10, "oct": 10, "november": 11,
}

GIORNI_SETTIMANA = {
    "lunedì": 0, "lunedi": 0, "montag": 0, "lundi": 0, "maandag": 0, "lunes": 0, "segunda-feira": 0, "segunda": 0, "monday": 0,
    "martedì": 1, "martedi": 1, "dienstag": 1, "mardi": 1, "dinsdag": 1, "martes": 1, "terça-feira": 1, "terça": 1, "terca-feira": 1, "tuesday": 1,
    "mercoledì": 2, "mercoledi": 2, "mittwoch": 2, "mercredi": 2, "woensdag": 2, "miércoles": 2, "miercoles": 2, "quarta-feira": 2, "quarta": 2, "wednesday": 2,
    "giovedì": 3, "giovedi": 3, "donnerstag": 3, "jeudi": 3, "donderdag": 3, "jueves": 3, "quinta-feira": 3, "quinta": 3, "thursday": 3,
    "venerdì": 4, "venerdi": 4, "freitag": 4, "vendredi": 4, "vrijdag": 4, "viernes": 4, "sexta-feira": 4, "sexta": 4, "friday": 4,
    "sabato": 5, "samstag": 5, "samedi": 5, "zaterdag": 5, "sábado": 5, "sabado": 5, "saturday": 5,
    "domenica": 6, "sonntag": 6, "dimanche": 6, "zondag": 6, "domingo": 6, "sunday": 6,
}

DAZN_PAESI = [
    {
        "paese": "DAZN Free Italia",
        "canale": "DAZN Free Italia",
        "tz": "Europe/Rome",
        "home": "https://www.dazn.com/it-IT/home",
        "wp_sites": [
            ("https://www.mondomobileweb.it", "DAZN Free"),
            ("https://www.tecnoandroid.it", "DAZN gratis"),
            ("https://www.webnews.it", "DAZN gratis"),
            ("https://www.telefonino.net", "DAZN gratis"),
        ],
        "bing_mkt": "it-IT",
        "bing_queries": ['"DAZN gratis" -site:dazn.com', '"DAZN free" Serie B OR volley -site:dazn.com'],
        "gnews": [
            ("it", "IT", "IT:it", '"DAZN gratis" OR "DAZN free" partite OR calendario -site:dazn.com'),
            ("it", "IT", "IT:it", '"DAZN" "senza abbonamento" partite OR calcio OR volley -site:dazn.com'),
        ],
    },
    {
        "paese": "DAZN Free Belgio",
        "canale": "DAZN Free Belgio",
        "tz": "Europe/Brussels",
        "home": "https://www.dazn.com/fr-BE/home",
        "wp_sites": [],
        "bing_mkt": "fr-BE",
        "bing_queries": ['"DAZN" "gratuit" Belgique -site:dazn.com', '"DAZN" "gratis" België -site:dazn.com'],
        "gnews": [
            ("fr", "BE", "BE:fr", '"DAZN" gratuit OR freemium -site:dazn.com'),
            ("nl", "BE", "BE:nl", '"DAZN" gratis OR freemium -site:dazn.com'),
        ],
    },
    {
        "paese": "DAZN Free Germania",
        "canale": "DAZN Free Germania",
        "tz": "Europe/Berlin",
        "home": "https://www.dazn.com/de-DE/home",
        "wp_sites": [],
        "bing_mkt": "de-DE",
        "bing_queries": ['"DAZN for free" OR "DAZN kostenlos" Programm -site:dazn.com'],
        "gnews": [
            ("de", "DE", "DE:de", '"DAZN for free" OR "DAZN kostenlos" -site:dazn.com'),
        ],
    },
    {
        "paese": "DAZN Free Canada",
        "canale": "DAZN Free Canada",
        "tz": "America/Toronto",
        "home": "https://www.dazn.com/en-CA/home",
        "wp_sites": [],
        "bing_mkt": "en-CA",
        "bing_queries": ['"DAZN" "for free" Canada OR NCAA -site:dazn.com'],
        "gnews": [
            ("en", "CA", "CA:en", '"DAZN" "for free" OR freemium -site:dazn.com'),
            ("en", "CA", "CA:en", '"DAZN" "watch free" OR "free game" -site:dazn.com'),
        ],
    },
    {
        "paese": "DAZN Free Giappone",
        "canale": "DAZN Free Giappone",
        "tz": "Asia/Tokyo",
        "home": "https://www.dazn.com/ja-JP/home",
        "wp_sites": [],
        "bing_mkt": "ja-JP",
        "bing_queries": ['"DAZN Freemium" 無料 -site:dazn.com', '"DAZN" "無料ライブ配信" -site:dazn.com'],
        "gnews": [
            ("ja", "JP", "JP:ja", '"DAZN Freemium" OR "DAZN 無料" -site:dazn.com'),
            ("ja", "JP", "JP:ja", '"DAZN" "無料配信" サッカー OR スポーツ -site:dazn.com'),
        ],
    },
    {
        "paese": "DAZN Free Spagna",
        "canale": "DAZN Free Spagna",
        "tz": "Europe/Madrid",
        "home": "https://www.dazn.com/es-ES/home",
        "wp_sites": [],
        "bing_mkt": "es-ES",
        "bing_queries": ['"DAZN App Gratis" -site:dazn.com', '"DAZN" "en abierto" gratis España -site:dazn.com'],
        "gnews": [
            ("es", "ES", "ES:es", '"DAZN App Gratis" OR "DAZN gratis" -site:dazn.com'),
            ("es", "ES", "ES:es", '"ver gratis en DAZN" partido -site:dazn.com'),
        ],
    },
    {
        "paese": "DAZN Free Portogallo",
        "canale": "DAZN Free Portogallo",
        "tz": "Europe/Lisbon",
        "home": "https://www.dazn.com/pt-PT/home",
        "wp_sites": [],
        "bing_mkt": "pt-PT",
        "bing_queries": ['"DAZN" "grátis" OR "em aberto" jogo Portugal -site:dazn.com'],
        "gnews": [
            ("pt-PT", "PT", "PT:pt-150", '"DAZN" grátis OR "em aberto" -site:dazn.com'),
            ("pt-PT", "PT", "PT:pt-150", '"ver grátis na DAZN" -site:dazn.com'),
        ],
    },
]

STOP_SECTIONS = [
    "notizie correlate", "related news", "related articles", "artigos relacionados",
    "noticias relacionadas", "articles liés", "ähnliche artikel", "weitere news",
    "meer nieuws", "関連記事", "notícias em destaque", "featured news",
]

IGNORE_LINES = [
    "abbonamento", "iscriviti", "registrati", "accedi", "cookie", "privacy",
    "copyright", "newsletter", "smart tv", "playstation", "xbox", "iphone", "ipad",
    "registrieren", "anmelden", "kostenlos anmelden", "jetzt anmelden", "werbung",
    "s'inscrire", "se connecter", "registrarse", "iniciar sesión", "regista-te",
    "sign up", "log in", "subscribe", "download the app", "無料登録", "ログイン",
    "comentar", "seguir", "leggi anche", "descarga", "baixa a app",
]

PROMO_BAD_WORDS = [
    "black friday", "cyber monday", "sconto", "prezzi", "tariffe", "abbonamenti",
    "1 mês grátis", "um mês grátis", "30 dias grátis", "reclamações", "fidelização",
    "free trial", "risparmiare", "kündigen", "verlosung", "gewinnspiel",
]

FREE_KEYWORDS = [
    "gratis", "free", "gratuit", "kostenlos", "freemium", "em aberto", "en abierto",
    "grátis", "in chiaro", "senza abbonamento", "ohne abo", "無料", "フリーミアム", "app gratis",
]

NEGATIVE_FREE_PHRASES = [
    "non è gratis", "non gratis", "nessuna diretta gratis", "keine kostenlose",
    "nicht kostenlos", "no es gratis", "solo a pagamento", "solo con abbonamento",
    "only with subscription", "abo nötig", "not free", "pay-tv",
]


def injetta_alt_immagini(soup):
    for img in soup.find_all("img"):
        lbl = (img.get("alt") or img.get("title") or "").strip()
        if lbl:
            img.replace_with(f" {lbl} ")
    for tag in soup.find_all(attrs={"title": True}):
        if not tag.get_text(strip=True):
            try:
                tag.append(f" {tag['title']} ")
            except Exception:
                pass


class SmartFetcher:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None

    def _ensure_browser(self):
        if self._browser is None and sync_playwright is not None:
            try:
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                self._context = self._browser.new_context(
                    user_agent=BROWSER_HEADERS["User-Agent"],
                    viewport={"width": 1366, "height": 768},
                )
                self._context.add_cookies([
                    {"name": "CONSENT", "value": "YES+cb.20210328-17-p0.en+FX+999", "domain": ".google.com", "path": "/"},
                    {"name": "SOCS", "value": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9zUjMaAmVuIAEaBgiA_LyaBg", "domain": ".google.com", "path": "/"},
                ])
            except Exception as e:
                print(f"⚠️ Impossibile avviare Chromium: {e}")

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    @staticmethod
    def _is_blocked_or_empty(html):
        if not html or len(html) < 700:
            return True
        low = html.lower()
        if "access denied" in low and ("akamai" in low or "reference #" in low):
            return True
        if "<title>access denied" in low or "just a moment..." in low or "cf-browser-verification" in low:
            return True
        if "consent.google.com" in low:
            return True
        soup = BeautifulSoup(html, "html.parser")
        title_txt = (soup.title.get_text(strip=True) if soup.title else "").lower()
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        vis_len = len(soup.get_text(" ", strip=True))
        if vis_len < 300:
            return True
        if title_txt == "dazn" and vis_len < 1200:
            return True
        return False

    def get_content(self, url, force_browser=False, allow_jina=True):
        if not force_browser and cffi_requests is not None:
            try:
                r = cffi_requests.get(url, impersonate="chrome", timeout=18, headers={"Accept-Language": "it-IT,it;q=0.9,en;q=0.8"})
                if r.status_code == 200 and not self._is_blocked_or_empty(r.text):
                    return ("html", r.text, "cffi")
            except Exception:
                pass

        if not force_browser and cffi_requests is None:
            try:
                r = requests.get(url, headers=BROWSER_HEADERS, timeout=18)
                if r.status_code == 200 and not self._is_blocked_or_empty(r.text):
                    return ("html", r.text, "req")
            except Exception:
                pass

        self._ensure_browser()
        if self._context is not None:
            page = None
            try:
                page = self._context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                page.wait_for_timeout(1200)
                html = page.content()
                if not self._is_blocked_or_empty(html):
                    return ("html", html, "pw")
            except Exception:
                pass
            finally:
                if page:
                    try:
                        page.close()
                    except Exception:
                        pass

        if allow_jina:
            try:
                rj = requests.get(f"https://r.jina.ai/{url}", timeout=15, headers={"User-Agent": BROWSER_HEADERS["User-Agent"]})
                if rj.status_code == 200 and len(rj.text) > 500 and "Access Denied" not in rj.text[:500] and "Just a moment" not in rj.text[:500]:
                    return ("markdown", rj.text, "jina")
            except Exception:
                pass

        return (None, None, "blocked")


def anno_vicino(mese, giorno, ref_dt=None):
    ref = ref_dt or NOW
    for y in (ref.year, ref.year + 1, ref.year - 1):
        try:
            cand = datetime(y, mese, giorno)
            if abs((cand.date() - ref.date()).days) <= 180:
                return y
        except ValueError:
            continue
    return ref.year


def estrai_data_da_testo(testo, ref_dt=None, month_first=False):
    ref = ref_dt or NOW
    t = (testo or "").strip()
    low = t.lower()

    if re.search(r"\b(oggi|heute|aujourd'hui|vandaag|hoy|hoje|today)\b", low) or "今日" in t or "本日" in t:
        return ref.date()
    if re.search(r"\b(domani|morgen|demain|mañana|amanhã|tomorrow)\b", low) or "明日" in t:
        return (ref + timedelta(days=1)).date()

    m = re.search(r"\b(202\d)[-/.年](\d{1,2})[-/.月](\d{1,2})日?", t)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            pass

    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](202\d)\b", t)
    if m:
        try:
            a, b, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
            mo, dy = (a, b) if (month_first and a <= 12) or b > 12 else (b, a)
            return datetime(yr, mo, dy).date()
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})月(\d{1,2})日", t)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
        try:
            return datetime(anno_vicino(mo, dy, ref), mo, dy).date()
        except ValueError:
            pass

    mesi_regex = "|".join(sorted(MESI_MAP.keys(), key=len, reverse=True))
    m = re.search(rf"\b(\d{{1,2}})\.?\s*(?:de\s+)?({mesi_regex})\.?(?:\s*(?:de\s+)?(202\d))?\b", low)
    if m:
        dy = int(m.group(1))
        mo = MESI_MAP[m.group(2)]
        yr = int(m.group(3)) if m.group(3) else anno_vicino(mo, dy, ref)
        try:
            return datetime(yr, mo, dy).date()
        except ValueError:
            pass

    m = re.search(rf"\b({mesi_regex})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(202\d))?\b", low)
    if m:
        mo = MESI_MAP[m.group(1)]
        dy = int(m.group(2))
        yr = int(m.group(3)) if m.group(3) else anno_vicino(mo, dy, ref)
        try:
            return datetime(yr, mo, dy).date()
        except ValueError:
            pass

    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(?!\s*\d)", t)
    if m:
        dy, mo = int(m.group(1)), int(m.group(2))
        if 1 <= dy <= 31 and 1 <= mo <= 12:
            try:
                return datetime(anno_vicino(mo, dy, ref), mo, dy).date()
            except ValueError:
                pass

    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        mo, dy = (a, b) if (month_first and a <= 12) or b > 12 else (b, a)
        if 1 <= mo <= 12 and 1 <= dy <= 31:
            try:
                return datetime(anno_vicino(mo, dy, ref), mo, dy).date()
            except ValueError:
                pass

    for g_nome, g_idx in GIORNI_SETTIMANA.items():
        if re.search(rf"\b{re.escape(g_nome)}\b", low):
            diff = (g_idx - ref.weekday()) % 7
            return (ref + timedelta(days=diff)).date()

    return None


def estrai_orario_da_testo(testo):
    t = (testo or "").strip()
    t_nodate = re.sub(r"\b(202\d)[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}[/.]\d{1,2}[/.]202\d\b|\b\d{1,2}\.\d{1,2}\.(?!\s*\d)|\b\d{1,2}/\d{1,2}\b", " ", t)
    low = t_nodate.lower()

    m = re.search(r"(\d{1,2})\s*時\s*(\d{2})?\s*分?", t_nodate)
    if m:
        return int(m.group(1)), int(m.group(2) or "0")

    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", low)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2) or "0")
        ampm = m.group(3)
        if ampm == "pm" and hh != 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        return hh, mm

    patterns = [
        r"\b([01]?\d|2[0-9]):([0-5]\d)\b",
        r"\b([01]?\d|2[0-9])\s*h\s*([0-5]\d)?\b",
        r"\b([01]?\d|2[0-3])[.]([0-5]\d)\b",
        r"\b([01]?\d|2[0-3])\s*uhr\b",
        r"\b(?:ore|alle|às|as|à|a las)\s+([01]?\d|2[0-3])(?:[:.h]([0-5]\d))?\b",
    ]
    for pat in patterns:
        m = re.search(pat, low)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2) or "0") if m.lastindex and m.lastindex >= 2 else 0
            return hh, mm
    return None


def risolvi_tz_linea(testo, default_tz_name):
    low = (testo or "").lower()
    if re.search(r"\b(bst|uk)\b", low):
        return ZoneInfo("Europe/London")
    if re.search(r"\b(gmt|utc)\b", low):
        return ZoneInfo("UTC")
    if re.search(r"\b(cet|cest|mez|mesz)\b", low):
        return ZoneInfo("Europe/Berlin")
    if re.search(r"\b(et|est|edt)\b", low):
        return ZoneInfo("America/Toronto")
    return ZoneInfo(default_tz_name)


def pulisci_evento_dazn(testo):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", testo or "")
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"^(?:#{1,6}\s+|[*•>\-]+\s+)", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—:|•·,")
    s = re.sub(r"^(?:esta|nesta|este|hoy|oggi|heute|today|this)\s+[^,]+,\s*", "", s, flags=re.I)
    s = re.sub(r"^(?:vê|ve|acompanha|assiste|guarda|mira|ver|watch|siehe|seht)\s+(?:em direto\s+)?(?:e\s+)?(?:grátis|gratis|for free|kostenlos|gratuitamente)\s+(?:o|a|os|as|lo|la|el)?\s*", "", s, flags=re.I)
    s = re.sub(r"^\d{1,2}[/.]\d{1,2}(?:[/.]202\d)?(?:\([日月火水木金土]\))?\s*[-–—,|•]*\s*", "", s)
    s = re.sub(r"^\d{1,2}月\d{1,2}日(?:\([日月火水木金土]\))?\s*[-–—,|•]*\s*", "", s)
    s = re.sub(r"^(?:ore|ab|às|as|à|um|kick-off)\s+", "", s, flags=re.I)
    s = re.sub(r"^\d{1,2}[:.h]\d{0,2}\s*(?:uhr|am|pm|et|est|cet|mez)?\s*[-–—:|•,]*\s*", "", s, flags=re.I)
    s = re.sub(r",?\s*(?:às|as|alle|à|a las|um|at)\s+\d{1,2}[:.h]?\d{0,2}\s*(?:uhr|am|pm)?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-–—|•]?\s*(?:dazn(?:\s+for\s+free|\s+freemium|\s+gratis)?)$", "", s, flags=re.I)
    return s.strip(" -–—:|•·,.")


def sembra_evento_valido(testo):
    if not testo or len(testo) < 6 or len(testo) > 150:
        return False
    if sum(c.isalpha() for c in testo) < 4:
        return False
    low = testo.lower()
    if any(bad in low for bad in IGNORE_LINES):
        return False
    if any(neg in low for neg in NEGATIVE_FREE_PHRASES):
        return False
    ha_sfida = bool(re.search(r"(\s+-\s+|\s+vs\.?\s+|\s+x\s+|\s+@\s+|–|[A-Za-zÀ-ÿ]-[A-Za-zÀ-ÿ])", testo, re.I))
    ha_sport = classifica_sport(testo, canale_solo_sport=False) is not None
    ha_parole_evento = any(w in low for w in [
        "women", "liga", "cup", "coppa", "grand prix", "fight", "boxing",
        "padel", "darts", "golf", "chess", "konferenz", "j1", "j2", "j3",
        "premier12", "ufc", "oktagon", "dtm",
    ])
    return ha_sfida or (ha_sport and len(testo) >= 10) or ha_parole_evento


def estrai_pub_date_articolo(soup):
    for sel in [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "publish-date"}),
        ("meta", {"property": "og:updated_time"}),
    ]:
        tag = soup.find(*sel)
        if tag and tag.get("content"):
            try:
                return datetime.fromisoformat(tag["content"][:19])
            except Exception:
                pass
    t_tag = soup.find("time")
    if t_tag and t_tag.get("datetime"):
        try:
            return datetime.fromisoformat(t_tag["datetime"][:19])
        except Exception:
            pass
    return None


def estrai_righe_da_soup(soup):
    for br in soup.find_all("br"):
        br.replace_with("\n")
    righe = []
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "div"]):
        if el.find(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "div"]):
            continue
        raw = el.get_text(" ")
        for sub in raw.splitlines():
            clean = re.sub(r"\s+", " ", sub).strip()
            if clean:
                righe.append(clean)
    return righe


def aggiungi_riga_tabella(cells, cfg, ref_dt, month_first, risultati):
    if len(cells) < 2:
        return
    riga_completa = " | ".join(cells)
    if any(neg in riga_completa.lower() for neg in NEGATIVE_FREE_PHRASES):
        return
    d = estrai_data_da_testo(riga_completa, ref_dt, month_first=month_first)
    hm = estrai_orario_da_testo(riga_completa)
    if not d or not hm:
        return
    hh, mm = hm
    extra_days = hh // 24
    hh = hh % 24
    tz = risolvi_tz_linea(riga_completa, cfg["tz"])
    try:
        dt_local = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz) + timedelta(days=extra_days)
        dt_it = dt_local.astimezone(ROME_TZ)
    except Exception:
        return
    if not (MIN_DT <= dt_it <= MAX_DT):
        return

    altre_celle = []
    for c in cells:
        if estrai_orario_da_testo(c) and len(c) < 32:
            continue
        if re.match(r"^(dazn|gratis|free)", c, re.I) and len(c) < 25:
            continue
        altre_celle.append(c)

    if not altre_celle:
        return
    if len(altre_celle) >= 2:
        ev_idx = next((i for i, x in enumerate(altre_celle) if re.search(r"\bvs\.?\b| - | @ | x ", x, re.I)), len(altre_celle) - 1)
        evento = pulisci_evento_dazn(altre_celle[ev_idx])
        comp = " • ".join(x for i, x in enumerate(altre_celle) if i != ev_idx)[:60] or "DAZN Free"
    else:
        evento = pulisci_evento_dazn(altre_celle[0])
        comp = "DAZN Free"

    if sembra_evento_valido(evento):
        sport = classifica_sport(f"{comp} {evento}", canale_solo_sport=True) or "Altri Sport"
        risultati.append({
            "data": dt_it.strftime("%Y-%m-%d"),
            "ora": dt_it.strftime("%H:%M"),
            "sport": sport,
            "competizione": comp,
            "evento": evento,
            "paese": cfg["paese"],
            "canale": cfg["canale"],
            "link": cfg["home"],
        })


def estrai_eventi_dazn_da_contenuto(kind, content, cfg, is_calendar_article=True, fallback_pub_dt=None):
    risultati = []
    month_first = cfg["tz"] in ("Asia/Tokyo", "America/Toronto")
    pub_dt = fallback_pub_dt
    page_title = ""
    max_d = None

    if kind == "html":
        soup = BeautifulSoup(content, "html.parser")
        if soup.title:
            page_title = soup.title.get_text(" ", strip=True)[:35]
        injetta_alt_immagini(soup)
        art_dt = estrai_pub_date_articolo(soup) or fallback_pub_dt
        ref_dt = art_dt.replace(tzinfo=None) if (art_dt and abs((NOW.replace(tzinfo=None) - art_dt.replace(tzinfo=None)).days) <= 21) else NOW.replace(tzinfo=None)

        for tr in soup.find_all("tr"):
            cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            if is_calendar_article or any(kw in " ".join(cells).lower() for kw in ["dazn", "gratis", "free"]):
                aggiungi_riga_tabella(cells, cfg, ref_dt, month_first, risultati)

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        righe = estrai_righe_da_soup(soup)
        txt_len = sum(len(x) for x in righe)
    else:
        ref_dt = pub_dt.replace(tzinfo=None) if (pub_dt and abs((NOW.replace(tzinfo=None) - pub_dt.replace(tzinfo=None)).days) <= 21) else NOW.replace(tzinfo=None)
        righe = [re.sub(r"\s+", " ", x).strip() for x in (content or "").splitlines() if x.strip()]
        txt_len = len(content or "")
        page_title = "markdown"

    current_date = None
    last_match_hint = ""
    pending_dt = None

    for line in righe:
        if line.startswith("|") and "|" in line[1:]:
            if re.match(r"^[\|\s:-]+$", line):
                continue
            cells = [p.strip() for p in line.strip("|").split("|") if p.strip()]
            if is_calendar_article or any(kw in line.lower() for kw in ["dazn", "gratis", "free"]):
                aggiungi_riga_tabella(cells, cfg, ref_dt, month_first, risultati)
            continue

        line_clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line_clean = re.sub(r"^(?:#{1,6}\s+|[*•>\-]+\s+)", "", line_clean).replace("**", "").strip()
        if any(stop in line_clean.lower() for stop in STOP_SECTIONS):
            break

        # Non spezza "27. November", "1. FC Köln", "St.", "vs."
        if len(line_clean) > 140:
            frasi = re.split(r"(?<!\b\d)(?<!\b\d\d)(?<!\bvs)(?<!\bSt)(?<=[.!?])\s+(?=[A-ZÀ-ÿ0-9])", line_clean)
        else:
            frasi = [line_clean]

        for frase in frasi:
            frase = frase.strip()
            if not frase:
                continue
            low = frase.lower()
            if any(bad in low for bad in IGNORE_LINES) and len(frase) < 95:
                continue
            if any(neg in low for neg in NEGATIVE_FREE_PHRASES):
                continue

            d_found = estrai_data_da_testo(frase, ref_dt, month_first=month_first)
            if d_found and (max_d is None or d_found > max_d):
                max_d = d_found
            hm_found = estrai_orario_da_testo(frase)

            if pending_dt and not hm_found and sembra_evento_valido(pulisci_evento_dazn(frase)):
                ev_p = pulisci_evento_dazn(frase)
                sport = classifica_sport(ev_p, canale_solo_sport=True) or "Altri Sport"
                risultati.append({
                    "data": pending_dt.strftime("%Y-%m-%d"),
                    "ora": pending_dt.strftime("%H:%M"),
                    "sport": sport,
                    "competizione": "DAZN Free",
                    "evento": ev_p,
                    "paese": cfg["paese"],
                    "canale": cfg["canale"],
                    "link": cfg["home"],
                })
                pending_dt = None
                continue
            pending_dt = None

            if d_found and not hm_found and len(frase) < 65:
                current_date = d_found
                continue

            if not hm_found and re.search(r"(\s+-\s+|\s+vs\.?\s+|\s+x\s+|\s+@\s+)", frase, re.I) and len(frase) < 90:
                last_match_hint = pulisci_evento_dazn(frase)
                continue

            if not is_calendar_article and "dazn" not in low:
                continue

            eff_date = d_found or current_date
            if eff_date and hm_found:
                hh, mm = hm_found
                extra_days = hh // 24
                hh = hh % 24
                tz = risolvi_tz_linea(frase, cfg["tz"])
                try:
                    dt_local = datetime(eff_date.year, eff_date.month, eff_date.day, hh, mm, tzinfo=tz) + timedelta(days=extra_days)
                    dt_it = dt_local.astimezone(ROME_TZ)
                except Exception:
                    continue
                if not (MIN_DT <= dt_it <= MAX_DT):
                    continue

                evento = pulisci_evento_dazn(frase)
                if (len(evento) < 6 or not sembra_evento_valido(evento)) and last_match_hint:
                    evento = last_match_hint
                    last_match_hint = ""
                elif len(evento) < 6 or not sembra_evento_valido(evento):
                    pending_dt = dt_it
                    continue

                if len(evento) > 135 or not sembra_evento_valido(evento):
                    continue
                sport = classifica_sport(evento, canale_solo_sport=True) or "Altri Sport"
                risultati.append({
                    "data": dt_it.strftime("%Y-%m-%d"),
                    "ora": dt_it.strftime("%H:%M"),
                    "sport": sport,
                    "competizione": "DAZN Free",
                    "evento": evento,
                    "paese": cfg["paese"],
                    "canale": cfg["canale"],
                    "link": cfg["home"],
                })

    max_d_str = max_d.strftime("%m-%d") if max_d else "-"
    return risultati, page_title, txt_len, max_d_str


def parse_rss_date(pub_str):
    try:
        return parsedate_to_datetime(pub_str).replace(tzinfo=None)
    except Exception:
        return None


def decodifica_gnews_url(url):
    if "news.google.com" not in url or _gnews_fn is None:
        return url, "no_fn"
    try:
        res = _gnews_fn(url, interval=1)
        if res and (res.get("status") or res.get("success")) and res.get("decoded_url"):
            return res["decoded_url"], "ok"
        return url, str(res.get("message", "fail"))[:25]
    except Exception as e:
        return url, str(e)[:25]


def cerca_wordpress_dazn(site_url, query, cfg):
    trovati = []
    try:
        r = requests.get(
            f"{site_url}/wp-json/wp/v2/posts?search={quote_plus(query)}&per_page=3",
            headers=BROWSER_HEADERS,
            timeout=14,
        )
        if r.status_code != 200:
            return []
        for post in r.json():
            titolo = BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text()
            low_t = titolo.lower()
            if "dazn" not in low_t or not any(fk in low_t for fk in FREE_KEYWORDS):
                continue
            if any(bad in low_t for bad in PROMO_BAD_WORDS):
                continue
            pub_dt = datetime.fromisoformat(post["date"][:19])
            if (NOW.replace(tzinfo=None) - pub_dt).days > 28:
                continue
            html = post.get("content", {}).get("rendered", "")
            ev, _, _, _ = estrai_eventi_dazn_da_contenuto("html", html, cfg, is_calendar_article=True, fallback_pub_dt=pub_dt)
            trovati.extend(ev)
    except Exception:
        pass
    return trovati


def cerca_bing_news(query, mkt):
    articoli = []
    url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss&mkt={mkt}"
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=18)
        if r.status_code != 200 or "<item>" not in r.text:
            return []
        root = ET.fromstring(r.text)
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            raw_link = (item.findtext("link") or "").strip()
            pub_str = (item.findtext("pubDate") or "").strip()
            qs = parse_qs(urlparse(raw_link).query)
            real_url = qs.get("url", [raw_link])[0]
            pub_dt = parse_rss_date(pub_str)
            if real_url:
                articoli.append((title, real_url, pub_dt))
    except Exception:
        pass
    return articoli


def cerca_google_news(query, hl, gl, ceid):
    articoli = []
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=18)
        if r.status_code != 200 or "<item>" not in r.text:
            return []
        root = ET.fromstring(r.text)
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_str = (item.findtext("pubDate") or "").strip()
            pub_dt = parse_rss_date(pub_str)
            if link:
                articoli.append((title, link, pub_dt))
    except Exception:
        pass
    return articoli


def scarica_dazn_tutti_paesi(fetcher):
    tutti = []
    for cfg in DAZN_PAESI:
        paese = cfg["paese"]
        print(f"⚡ Cerco eventi gratuiti per {paese}...")
        eventi_paese = []
        candidati = []
        visti_url = set()

        wp_ev = 0
        for wp_site, wp_q in cfg.get("wp_sites", []):
            ev_wp = cerca_wordpress_dazn(wp_site, wp_q, cfg)
            wp_ev += len(ev_wp)
            eventi_paese.extend(ev_wp)

        bing_n = 0
        for bq in cfg.get("bing_queries", []):
            for title, u, pub_dt in cerca_bing_news(bq, cfg["bing_mkt"]):
                low_t = title.lower()
                if any(bad in low_t for bad in PROMO_BAD_WORDS):
                    continue
                if pub_dt and (NOW.replace(tzinfo=None) - pub_dt).days > 25:
                    continue
                if "dazn" in low_t and any(fk in low_t for fk in FREE_KEYWORDS):
                    if u not in visti_url:
                        visti_url.add(u)
                        candidati.append((title, u, pub_dt, True))
                        bing_n += 1

        gnews_raw = 0
        gnews_dec = 0
        last_g_err = ""
        for hl, gl, ceid, gq in cfg.get("gnews", []):
            for title, raw_u, pub_dt in cerca_google_news(gq, hl, gl, ceid):
                low_t = title.lower()
                if any(bad in low_t for bad in PROMO_BAD_WORDS):
                    continue
                if pub_dt and (NOW.replace(tzinfo=None) - pub_dt).days > 25:
                    continue
                if "dazn" in low_t and any(fk in low_t for fk in FREE_KEYWORDS):
                    gnews_raw += 1
                    if gnews_dec >= 5:
                        continue
                    decoded_u, status_msg = decodifica_gnews_url(raw_u)
                    if "news.google.com" in decoded_u:
                        last_g_err = status_msg
                        continue
                    gnews_dec += 1
                    if decoded_u not in visti_url:
                        visti_url.add(decoded_u)
                        candidati.append((title, decoded_u, pub_dt, True))

        logs_pag = []
        for title, page_url, pub_dt, is_cal in candidati[:7]:
            kind, content, via = fetcher.get_content(page_url, allow_jina=True)
            if not content:
                logs_pag.append(f"{via}:0")
                continue
            trovati, p_title, txt_len, max_d = estrai_eventi_dazn_da_contenuto(
                kind, content, cfg, is_calendar_article=is_cal, fallback_pub_dt=pub_dt
            )
            logs_pag.append(f"{via}:{p_title[:14]}({txt_len}c,m={max_d})->{len(trovati)}")
            eventi_paese.extend(trovati)

        g_info = f"{gnews_dec}/{gnews_raw}" + (f"({last_g_err})" if last_g_err else "")
        print(f"   🔎 [{paese}] wp={wp_ev}, bing={bing_n}, gnews={g_info} | {' ; '.join(logs_pag)} => TOT {len(eventi_paese)}")
        tutti.extend(eventi_paese)
    return tutti


# ------------------------------------------------------------------------------
# GUIDE TV DIRETTE: ITALIA (Digital-News), SPAGNA (MundoDeportivo + DondeVerlo),
# GERMANIA (FussballGucken), GIAPPONE (ABEMA)
# ------------------------------------------------------------------------------
def scarica_dazn_italia_digitalnews(fetcher):
    risultati = []
    print("🇮🇹⚡ Controllo Digital-News.it (DAZN Free Italia)...")
    kind, html, via = fetcher.get_content("https://www.digital-news.it/news/dazn/", allow_jina=True)
    if not html or kind != "html":
        print(f"   🔎 [Digital-News IT] ({via}) -> 0 eventi")
        return risultati

    soup = BeautifulSoup(html, "html.parser")
    links = []
    visti = set()
    for a in soup.find_all("a", href=True):
        href = urljoin("https://www.digital-news.it/", a["href"])
        txt = a.get_text(" ", strip=True)
        low_all = (href + " " + txt).lower()
        if "dazn" in low_all and any(k in low_all for k in ["gratis", "free", "in chiaro", "freezone"]):
            if href not in visti and not any(b in low_all for b in PROMO_BAD_WORDS):
                visti.add(href)
                links.append(href)

    cfg_it = next(c for c in DAZN_PAESI if c["paese"] == "DAZN Free Italia")
    for u in links[:4]:
        k2, c2, _ = fetcher.get_content(u, allow_jina=True)
        if c2:
            ev, _, _, _ = estrai_eventi_dazn_da_contenuto(k2, c2, cfg_it, is_calendar_article=True)
            risultati.extend(ev)

    print(f"   🔎 [Digital-News IT] ({via}, art={len(links[:4])}) -> trovati {len(risultati)} eventi")
    return risultati


def scarica_dazn_spagna_guide(fetcher):
    risultati = []
    print("🇪🇸⚡ Controllo Mundo Deportivo Guía TV + Dónde Verlo (DAZN App Gratis ES)...")
    vias = []

    # 1) Mundo Deportivo Guía TV (Hoy + Esta Semana)
    for md_url in [
        "https://www.mundodeportivo.com/guia-tv/futbol-hoy",
        "https://www.mundodeportivo.com/guia-tv/futbol-esta-semana",
    ]:
        kind, content, via = fetcher.get_content(md_url, allow_jina=True)
        vias.append(f"md:{via}")
        if not content:
            continue
        if kind == "html":
            soup = BeautifulSoup(content, "html.parser")
            injetta_alt_immagini(soup)
            lines = estrai_righe_da_soup(soup)
        else:
            lines = [re.sub(r"\s+", " ", x).strip() for x in content.splitlines() if x.strip()]

        current_date = NOW.date()
        for i, line in enumerate(lines):
            d_cand = estrai_data_da_testo(line, NOW.replace(tzinfo=None))
            if d_cand and len(line) < 55 and not estrai_orario_da_testo(line):
                current_date = d_cand
                continue
            if "dazn app gratis" in line.lower():
                # Cerca orario e squadre nella riga stessa o nelle 3 righe precedenti
                blocco = " | ".join(lines[max(0, i - 3): i + 1])
                hm = estrai_orario_da_testo(blocco)
                d_row = estrai_data_da_testo(blocco, NOW.replace(tzinfo=None)) or current_date
                if hm:
                    hh, mm = hm
                    try:
                        dt_es = datetime(d_row.year, d_row.month, d_row.day, hh, mm, tzinfo=ZoneInfo("Europe/Madrid"))
                        dt_it = dt_es.astimezone(ROME_TZ)
                        if MIN_DT <= dt_it <= MAX_DT:
                            ev = pulisci_evento_dazn(re.sub(r"DAZN.*", "", blocco, flags=re.I))
                            ev = re.sub(r"\s*\|\s*", " ", ev).strip()
                            if sembra_evento_valido(ev):
                                risultati.append({
                                    "data": dt_it.strftime("%Y-%m-%d"),
                                    "ora": dt_it.strftime("%H:%M"),
                                    "sport": classifica_sport(ev, canale_solo_sport=True) or "Calcio",
                                    "competizione": "DAZN Free Spagna",
                                    "evento": ev,
                                    "paese": "DAZN Free Spagna",
                                    "canale": "DAZN App Gratis (ES)",
                                    "link": "https://www.dazn.com/es-ES/home",
                                })
                    except Exception:
                        pass

    # 2) Dónde Verlo (canali DAZN Spagna)
    for dv_url in ["https://dondeverlo.com/canales/dazn", "https://dondeverlo.com/canales/dazn-app-gratis"]:
        kind, content, via = fetcher.get_content(dv_url, allow_jina=True)
        vias.append(f"dv:{via}")
        if not content:
            continue
        if kind == "html":
            soup = BeautifulSoup(content, "html.parser")
            injetta_alt_immagini(soup)
            lines = estrai_righe_da_soup(soup)
        else:
            lines = [re.sub(r"\s+", " ", x).strip() for x in content.splitlines() if x.strip()]

        solo_gratis = dv_url.endswith("/dazn")
        for i, line in enumerate(lines):
            if solo_gratis and "dazn app gratis" not in line.lower():
                continue
            d_row = estrai_data_da_testo(line, NOW.replace(tzinfo=None))
            hm = estrai_orario_da_testo(line)
            if d_row and hm:
                hh, mm = hm
                try:
                    dt_es = datetime(d_row.year, d_row.month, d_row.day, hh, mm, tzinfo=ZoneInfo("Europe/Madrid"))
                    dt_it = dt_es.astimezone(ROME_TZ)
                    if MIN_DT <= dt_it <= MAX_DT:
                        ev = re.sub(r"Escudo\s+\S+\s*", "", line)
                        ev = pulisci_evento_dazn(re.sub(r"(?:DAZN|M\+|Orange|LaLiga TV|RTVE).*", "", ev, flags=re.I))
                        if sembra_evento_valido(ev):
                            risultati.append({
                                "data": dt_it.strftime("%Y-%m-%d"),
                                "ora": dt_it.strftime("%H:%M"),
                                "sport": classifica_sport(ev, canale_solo_sport=True) or "Calcio",
                                "competizione": "DAZN Free Spagna",
                                "evento": ev,
                                "paese": "DAZN Free Spagna",
                                "canale": "DAZN App Gratis (ES)",
                                "link": "https://www.dazn.com/es-ES/home",
                            })
                except Exception:
                    pass

    print(f"   🔎 [Spagna Guide MD+DV] ({','.join(vias)}) -> trovati {len(risultati)} eventi")
    return risultati


def scarica_dazn_germania_fussballgucken(fetcher):
    risultati = []
    print("🇩🇪⚡ Controllo FussballGucken.info (Dirette gratis DAZN Germania)...")
    _, home_html, via_home = fetcher.get_content("https://www.fussballgucken.info/", allow_jina=True)
    if not home_html:
        print(f"   🔎 [FussballGucken DE] home={via_home} -> 0 eventi")
        return risultati

    urls = set()
    soup = BeautifulSoup(home_html, "html.parser")
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True).lower()
        href = urljoin("https://www.fussballgucken.info/", a["href"])
        if "free-tv" in href.lower() or "free-tv" in txt:
            urls.add(href)

    if not urls:
        urls.add("https://www.fussballgucken.info/free-tv")

    vias = []
    for u in list(urls)[:3]:
        kind, content, via = fetcher.get_content(u, allow_jina=True)
        vias.append(via)
        if not content:
            continue
        if kind == "html":
            csoup = BeautifulSoup(content, "html.parser")
            injetta_alt_immagini(csoup)
            testo = csoup.get_text("\n")
        else:
            testo = content
        lines = [re.sub(r"\s+", " ", x).strip() for x in testo.splitlines() if x.strip()]

        current_date = NOW.date()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_d = re.search(r"\b(\d{2}\.\d{2}\.202\d)\b", line)
            if m_d and len(line) < 55:
                try:
                    current_date = datetime.strptime(m_d.group(1), "%d.%m.%Y").date()
                except Exception:
                    pass
                i += 1
                continue

            m_hm = re.match(r"^(\d{2}):(\d{2})(?:\s*Uhr)?\b", line)
            if m_hm:
                hh, mm = int(m_hm.group(1)), int(m_hm.group(2))
                blocco = []
                j = i + 1
                while j < len(lines) and j <= i + 18 and not re.match(r"^\d{2}:\d{2}(?:\s*Uhr)?\b", lines[j]) and not re.search(r"\b\d{2}\.\d{2}\.202\d\b", lines[j]):
                    blocco.append(lines[j])
                    j += 1

                blocco_txt = " | ".join(blocco)
                if "dazn" in blocco_txt.lower():
                    comp = blocco[0] if blocco else "Calcio"
                    evento = ""
                    for k, b in enumerate(blocco):
                        if b in ("·", "-", "vs", "vs.") and 0 < k < len(blocco) - 1:
                            evento = f"{blocco[k-1]} vs {blocco[k+1]}"
                            break
                    if not evento:
                        match_line = next((b for b in blocco if (" · " in b or " - " in b or " vs " in b.lower()) and "dazn" not in b.lower() and "sender" not in b.lower()), "")
                        evento = match_line.replace(" · ", " vs ") if match_line else ""
                    if not evento:
                        squadre = [b for b in blocco[1:] if not any(w in b.lower() for w in ["spieltag", "dazn", "sender", "option", "free-tv", "live", "konferenz", "gruppe", "runde", "fifa+"]) and len(b) > 2]
                        if len(squadre) >= 2:
                            evento = f"{squadre[0]} vs {squadre[1]}"
                        elif len(squadre) == 1:
                            evento = squadre[0]

                    try:
                        dt_de = datetime(current_date.year, current_date.month, current_date.day, hh, mm, tzinfo=ZoneInfo("Europe/Berlin"))
                        dt_it = dt_de.astimezone(ROME_TZ)
                        if MIN_DT <= dt_it <= MAX_DT and sembra_evento_valido(evento):
                            sport = classifica_sport(f"{comp} {evento}", canale_solo_sport=True) or "Calcio"
                            risultati.append({
                                "data": dt_it.strftime("%Y-%m-%d"),
                                "ora": dt_it.strftime("%H:%M"),
                                "sport": sport,
                                "competizione": comp,
                                "evento": evento,
                                "paese": "DAZN Free Germania",
                                "canale": "DAZN Free Germania",
                                "link": "https://www.dazn.com/de-DE/home",
                            })
                    except Exception:
                        pass
                i = j
                continue
            i += 1

    print(f"   🔎 [FussballGucken DE] ({','.join(vias)}) -> trovati {len(risultati)} eventi")
    return risultati


def scarica_abema_giappone(fetcher):
    risultati = []
    print("🇯🇵📺 Controllo ABEMA Free Giappone...")
    urls = ["https://www.soccer-king.jp/league/bundesliga"]
    for title, raw_u, pub_dt in cerca_google_news('"ABEMA" "無料" ブンデスリーガ', "ja", "JP", "JP:ja"):
        if pub_dt and (NOW.replace(tzinfo=None) - pub_dt).days <= 14:
            u, _ = decodifica_gnews_url(raw_u)
            if "news.google.com" not in u and u not in urls:
                urls.append(u)
            if len(urls) >= 4:
                break

    vias = []
    for u in urls:
        kind, content, via = fetcher.get_content(u, allow_jina=True)
        vias.append(via)
        if not content or kind != "html":
            continue
        soup = BeautifulSoup(content, "html.parser")
        injetta_alt_immagini(soup)
        for line in estrai_righe_da_soup(soup):
            if "abema" in line.lower() and ("無料" in line or "vs" in line.lower()) and "abema de dazn" not in line.lower():
                d = estrai_data_da_testo(line, NOW.astimezone(JP_TZ).replace(tzinfo=None), month_first=True)
                hm = estrai_orario_da_testo(line)
                if d and hm:
                    hh, mm = hm
                    extra_days = hh // 24
                    hh = hh % 24
                    try:
                        dt_jp = datetime(d.year, d.month, d.day, hh, mm, tzinfo=JP_TZ) + timedelta(days=extra_days)
                        dt_it = dt_jp.astimezone(ROME_TZ)
                        if MIN_DT <= dt_it <= MAX_DT:
                            ev = pulisci_evento_dazn(re.sub(r"(?:ABEMA|無料配信|実況|解説).*", "", line))
                            if sembra_evento_valido(ev):
                                risultati.append({
                                    "data": dt_it.strftime("%Y-%m-%d"),
                                    "ora": dt_it.strftime("%H:%M"),
                                    "sport": classifica_sport(ev, canale_solo_sport=True) or "Calcio",
                                    "competizione": "ABEMA Free Giappone",
                                    "evento": ev,
                                    "paese": "Giappone ABEMA Free",
                                    "canale": "ABEMA Free (JP)",
                                    "link": "https://abema.tv/video/genre/sports",
                                })
                    except Exception:
                        pass
    print(f"   🔎 [ABEMA JP] ({','.join(vias)}) -> trovati {len(risultati)} eventi")
    return risultati


# ==============================================================================
# 5) EVENTI MANUALI + DEDUPLICAZIONE + SALVATAGGIO
# ==============================================================================
def carica_manuali():
    if not os.path.exists("eventi_manuali.json"):
        return []
    try:
        with open("eventi_manuali.json", "r", encoding="utf-8") as f:
            dati = json.load(f)
        validi = [ev for ev in dati if ev.get("data", "") >= NOW.strftime("%Y-%m-%d")]
        print(f"📝 Caricati {len(validi)} eventi da eventi_manuali.json")
        return validi
    except Exception as e:
        print(f"⚠️ Errore in eventi_manuali.json: {e}")
        return []


def deduplica(eventi):
    visti = set()
    puliti = []
    for ev in eventi:
        titolo_base = ev.get("evento", "").split(":", 1)[-1].lower()
        titolo_base = re.sub(r"\b(fc|sc|ec|cr|ca)\b", "", titolo_base)
        chiave = (
            ev.get("data", ""),
            ev.get("ora", ""),
            ev.get("paese", ""),
            re.sub(r"[^a-z0-9]", "", titolo_base)[:22],
        )
        if chiave not in visti:
            visti.add(chiave)
            puliti.append(ev)
    puliti.sort(key=lambda x: (x.get("data", ""), x.get("ora", ""), x.get("paese", "")))
    return puliti


def main():
    tutti = []
    tutti.extend(scarica_epg_paesi())
    tutti.extend(scarica_futebol_tv_br())
    tutti.extend(scarica_auvaromaia_br())
    tutti.extend(scarica_gfesporte_br())

    fetcher = SmartFetcher()
    try:
        tutti.extend(scarica_dazn_tutti_paesi(fetcher))
        tutti.extend(scarica_dazn_italia_digitalnews(fetcher))
        tutti.extend(scarica_dazn_spagna_guide(fetcher))
        tutti.extend(scarica_dazn_germania_fussballgucken(fetcher))
        tutti.extend(scarica_abema_giappone(fetcher))
    finally:
        fetcher.close()

    tutti.extend(carica_manuali())

    finali = deduplica(tutti)

    if len(finali) > 0:
        with open("eventi.json", "w", encoding="utf-8") as f:
            json.dump(finali, f, ensure_ascii=False, indent=2)
        with open("meta.json", "w", encoding="utf-8") as f:
            json.dump({
                "ultimo_aggiornamento": NOW.strftime("%d/%m/%Y alle %H:%M"),
                "totale_eventi": len(finali),
            }, f, ensure_ascii=False, indent=2)
        print(f"🎉 Salvati {len(finali)} eventi totali in eventi.json!")
    else:
        print("⚠️ Nessun evento raccolto, mantengo il vecchio eventi.json.")


if __name__ == "__main__":
    main()
