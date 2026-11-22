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
# Puoi aggiungerne altri prendendo i codici da: https://epgshare01.online/epgshare01/
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
# 2) CANALI YOUTUBE BRASILIANI GRATUITI (puoi aggiungerne quanti ne vuoi!)
# Formato: (Nome mostrato sul sito, Link YouTube, [parole chiave per riconoscerlo])
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
# CLASSIFICATORE AUTOMATICO DEGLI SPORT
# ==============================================================================
PAROLE_DA_ESCLUDERE = [
    "telegiornale", "tg sport", "tg1", "tg2", "tg3", "sport mediaset",
    "sportmediaset", "tagesschau", "heute-journal", "meteo", "previsioni",
    "teleshopping", "rubrica", "cortes", "podcast", "resenha",
]

REGOLE_SPORT = [
    ("College Football", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b", r"\bncaa\b.*futebol americano"]),
    ("Football Americano", [r"\bnfl\b", r"\bfutebol americano\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bsuper bowl\b", r"\bran football\b"]),
    ("Formula 1", [r"\bformula 1\b", r"\bf[óo]rmula 1\b", r"\bformula uno\b", r"\bformel 1\b", r"\bformule 1\b", r"\bf1\b", r"\bgran premio di f1\b", r"\bgarage f1\b"]),
    ("MotoGP", [r"\bmotogp\b", r"\bmoto gp\b", r"\bmoto2\b", r"\bmoto3\b", r"\bmotomondiale\b", r"\bsuperbike\b", r"\bwsbk\b"]),
    ("Sci Alpino", [r"\bsci alpino\b", r"\bski alpin\b", r"\bski weltcup\b", r"\bski-weltcup\b", r"\bslalom\b", r"\bdiscesa libera\b", r"\bsuper-g\b", r"\bsuper g\b", r"\briesenslalom\b", r"\babfahrt\b", r"\bcoppa del mondo di sci\b"]),
    ("Pallavolo", [r"\bpallavolo\b", r"\bvolley\b", r"\bvolleyball\b", r"\bv[ôo]lei\b", r"\bsuperlega\b", r"\bsuperliga\b", r"\blvf\b", r"\bvnl\b"]),
    ("Basket & NBA", [r"\bnba\b", r"\bwnba\b", r"\bbasket\b", r"\bbasquete\b", r"\bpallacanestro\b", r"\bbasketball\b", r"\beurolega\b", r"\beuroleague\b", r"\beurocup\b", r"\beuroliga\b", r"\bnbb\b", r"\bfiba\b", r"\blega basket\b", r"\bbbl\b"]),
    ("Tennis", [r"\btennis\b", r"\bt[êe]nis\b", r"\batp\b", r"\bwta\b", r"\bcoppa davis\b", r"\bdavis cup\b", r"\bbillie jean king\b", r"\broland garros\b", r"\bwimbledon\b", r"\baustralian open\b", r"\bus open\b", r"\bchallenger\b"]),
    ("Calcio", [
        r"\bcalcio\b", r"\bfutebol\b", r"\bfu[ßs]ball\b", r"\bserie a\b",
        r"\bserie b\b", r"\bs[ée]rie b\b", r"\bcoppa italia\b", r"\bsupercoppa\b",
        r"\bchampions league\b", r"\beuropa league\b", r"\bconference league\b",
        r"\bnations league\b", r"\bmondiali\b", r"\bpremier league\b", r"\bbundesliga\b",
        r"\bdfb-pokal\b", r"\bdfb pokal\b", r"\blaliga\b", r"\bla liga\b", r"\bligue 1\b",
        r"\bbrasileir[ãa]o\b", r"\bpaulist[ãa]o\b", r"\bcarioca\b", r"\bcopa do brasil\b",
        r"\blibertadores\b", r"\bsul-americana\b", r"\bsudamericana\b", r"\bsuper league\b",
        r"\bchallenge league\b", r"\bcoppa svizzera\b", r"\bschweizer cup\b",
        r"\bsaudi pro league\b", r"\bmls\b", r"\bliga mx\b", r"\beredivisie\b",
        r"\bfa cup\b", r"\bcopa del rey\b", r"\bfutsal\b", r"\bnwsl\b", r"\bwsl\b",
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
    if canale_solo_sport and re.search(r"\b(x|vs\.?)\b", t):
        return "Calcio"
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


def risolvi_canali_br(testo_canali):
    t = (testo_canali or "").lower()
    trovati = []
    visti = set()
    for nome_uff, link, patterns in CANALI_BR_INFO:
        if any(re.search(pat, t) for pat in patterns):
            if nome_uff not in visti:
                visti.add(nome_uff)
                trovati.append((nome_uff, link))

    # Se non è tra i soliti noti, cattura comunque altri canali YouTube tipo "YouTube (FMF TV)"
    if not trovati:
        for m in re.finditer(r"youtube\s*\(([^)]+)\)", testo_canali or "", re.IGNORECASE):
            nome_extra = m.group(1).strip()
            if nome_extra:
                label = f"{nome_extra} (YouTube)"
                if label not in visti:
                    visti.add(label)
                    trovati.append((label, f"https://www.youtube.com/results?search_query={quote_plus(nome_extra)}"))
    return trovati


# ------------------------------------------------------------------------------
# SORGENTE BRASILIANA 1: futebol.tv.br (Tutta la settimana per canale YouTube!)
# ------------------------------------------------------------------------------
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

    print(f"🔎 Trovate {len(pagine_canali)} pagine canale su futebol.tv.br")

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
                # Pulisci eventuali residui
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


# ------------------------------------------------------------------------------
# SORGENTE BRASILIANA 2 & 3: AuvaroMaia & GFEsporte (TUTTI GLI SPORT BR!)
# ------------------------------------------------------------------------------
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

        # Riconosce titoli di sezione come "VÔLEI", "BASQUETE", "FUTEBOL AMERICANO", "AUTOMOBILISMO"
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

        # Formato tipico: "18h30 – Superliga Feminina: Mackenzie x Brusque – Ge TV"
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

        # Separa competizione ed evento se c'è ":" (es. "Superliga: Team A x Team B")
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

        # Unisce i nomi se più canali YouTube lo trasmettono (es. "CazéTV / Xsports")
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
    print("🇧🇷 Controllo AuvaroMaia (Calcio, Volley, Basket/NBA, Futsal, Tennis, Motori)...")
    try:
        r = requests.get(
            "https://auvaromaia.com/wp-json/wp/v2/posts?search=Agenda+esportiva&per_page=7",
            headers=BROWSER_HEADERS,
            timeout=25,
        )
        r.raise_for_status()
        posts = r.json()
        for post in posts:
            titolo = BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text()
            if "agenda esportiva" not in titolo.lower():
                continue
            pub_dt = datetime.fromisoformat(post["date"][:19])
            base_dt = risolvi_data_post_br(pub_dt, titolo)
            html = post.get("content", {}).get("rendered", "")
            risultati.extend(estrai_eventi_da_html_br(html, base_dt))
    except Exception as e:
        print(f"⚠️ API AuvaroMaia non disponibile ({e}), provo RSS...")
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


# ------------------------------------------------------------------------------
# DAZN FREE ITALIA + MANUALI
# ------------------------------------------------------------------------------
def scarica_dazn_free_italia():
    url = "https://www.dazn.com/it-IT/news/altro/come-funziona-la-modalita-free-su-dazn-e-come-attivarla/1n63xr4bv4gb8zw0uwdeq9cdq"
    print("⚡ Controllo pagina ufficiale DAZN Free Italia...")
    risultati = []
    try:
        resp = requests.get(url, timeout=30, headers={
            "User-Agent": BROWSER_HEADERS["User-Agent"],
            "Accept-Language": "it-IT,it;q=0.9",
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tr in soup.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            m = re.search(r"(\d{2}/\d{2}/\d{4})\s*[-–]?\s*(\d{2}:\d{2})", cells[0])
            if not m:
                continue
            dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M").replace(tzinfo=ROME_TZ)
            if not (MIN_DT <= dt <= MAX_DT):
                continue
            comp = cells[1]
            evento = cells[2]
            sport = classifica_sport(f"{comp} {evento}", canale_solo_sport=True) or "Altri Sport"
            risultati.append({
                "data": dt.strftime("%Y-%m-%d"),
                "ora": dt.strftime("%H:%M"),
                "sport": sport,
                "competizione": comp,
                "evento": evento,
                "paese": "DAZN Free",
                "canale": "DAZN Free Italia",
                "link": "https://www.dazn.com/it-IT/home",
            })
        print(f"✅ DAZN Free Italia: trovati {len(risultati)} eventi")
    except Exception as e:
        print(f"⚠️ DAZN Free Italia non raggiungibile automaticamente ({e})")
    return risultati


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
    tutti.extend(scarica_dazn_free_italia())
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
