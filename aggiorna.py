import gzip, io, json, os, re, xml.etree.ElementTree as ET
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

ROME_TZ, BR_TZ, JP_TZ = ZoneInfo("Europe/Rome"), ZoneInfo("America/Sao_Paulo"), ZoneInfo("Asia/Tokyo")
NOW = datetime.now(ROME_TZ)
MIN_DT = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
MAX_DT = NOW + timedelta(days=7)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36", "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"}
SOCIAL_BLACKLIST = ["instagram.com", "tiktok.com", "facebook.com", "fb.watch", "twitter.com", "x.com", "reddit.com", "youtube.com", "youtu.be", "threads.net", "linkedin.com", "dazn.com"]

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

PAROLE_DA_ESCLUDERE = ["telegiornale", "tg sport", "tg1", "tg2", "tg3", "sport mediaset", "sportmediaset", "tagesschau", "heute-journal", "meteo", "previsioni", "teleshopping", "rubrica", "cortes", "podcast", "resenha"]
REGOLE_SPORT = [
    ("College Football", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b"]),
    ("Football Americano", [r"\bnfl\b", r"\bfoot us\b", r"\bfutebol americano\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bfútbol americano\b", r"\bsuper bowl\b", r"\bran football\b", r"\bflag football\b", r"redzone", r"アメフト"]),
    ("Formula 1", [r"\bformula 1\b", r"\bf[óo]rmula 1\b", r"\bformula uno\b", r"\bformel 1\b", r"\bformule 1\b", r"\bf1\b", r"\bgran premio di f1\b", r"\bgarage f1\b"]),
    ("MotoGP", [r"\bmotogp\b", r"\bmoto gp\b", r"\bmoto2\b", r"\bmoto3\b", r"\bmotomondiale\b", r"\bsuperbike\b", r"\bwsbk\b"]),
    ("Sci Alpino", [r"\bsci alpino\b", r"\bski alpin\b", r"\bski weltcup\b", r"\bski-weltcup\b", r"\bslalom\b", r"\bdiscesa libera\b", r"\bsuper-g\b", r"\bsuper g\b", r"\briesenslalom\b", r"\babfahrt\b", r"\bcoppa del mondo di sci\b"]),
    ("Pallavolo", [r"\bpallavolo\b", r"\bvolley\b", r"\bvolleyball\b", r"\bv[ôo]lei\b", r"\bsuperlega\b", r"\bsuperliga\b", r"\blvf\b", r"\bvnl\b", r"\bserie a1\b", r"\bserie a2\b", r"バレー"]),
    ("Basket & NBA", [r"\bnba\b", r"\bwnba\b", r"\bbasket\b", r"\bbasquete\b", r"\bbaloncesto\b", r"\bpallacanestro\b", r"\bbasketball\b", r"\beurolega\b", r"\beuroleague\b", r"\beurocup\b", r"\beuroliga\b", r"\bnbb\b", r"\bfiba\b", r"\blega basket\b", r"\bliga endesa\b", r"\bliga acb\b", r"\bliga betclic\b", r"\bmarch madness\b", r"\bbbl\b", r"バスケ", r"bリーグ"]),
    ("Tennis", [r"\btennis\b", r"\bt[êe]nis\b", r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bcoppa davis\b", r"\bdavis cup\b", r"\bbillie jean king\b", r"\broland garros\b", r"\bwimbledon\b", r"\baustralian open\b", r"\bus open\b", r"\bchallenger\b", r"テニス"]),
    ("Calcio", [r"\bcalcio\b", r"\bfutebol\b", r"\bf[úu]tbol\b", r"\bfootball\b", r"\bsoccer\b", r"\bfu[ßs]ball\b", r"\bvoetbal\b", r"\bserie a\b", r"\bserie b\b", r"\bs[ée]rie b\b", r"\bcoppa italia\b", r"\bsupercoppa\b", r"\bchampions league\b", r"\beuropa league\b", r"\bconference league\b", r"\bnations league\b", r"\bmondiali\b", r"\bpremier league\b", r"\bbundesliga\b", r"\bdfb-pokal\b", r"\bdfb pokal\b", r"\blaliga\b", r"\bla liga\b", r"\bligue 1\b", r"\bbrasileir[ãa]o\b", r"\bpaulist[ãa]o\b", r"\bcarioca\b", r"\bcopa do brasil\b", r"\blibertadores\b", r"\bsul-americana\b", r"\bsudamericana\b", r"\bsuper league\b", r"\bjupiler\b", r"\bchallenger pro league\b", r"\bcroky cup\b", r"\bliga f\b", r"\buwcl\b", r"\bfrauen-bundesliga\b", r"\bfrauen bundesliga\b", r"\bserie a women\b", r"\bserie a femminile\b", r"\bliga portugal\b", r"\bnational league\b", r"\bfa cup\b", r"\bcopa del rey\b", r"\bfutsal\b", r"\bfifa\b", r"\bkings league\b", r"\byouth league\b", r"\bu17-wm\b", r"\bu-17\b", r"\bjリーグ\b", r"\bj1\b", r"\bj2\b", r"\bj3\b", r"サッカー", r"セリエa", r"ラリーガ", r"ブンデスリーガ", r"リーグアン", r"ベルギーリーグ"]),
]

MESI_MAP = {"gennaio": 1, "gen": 1, "febbraio": 2, "feb": 2, "marzo": 3, "mar": 3, "aprile": 4, "apr": 4, "maggio": 5, "mag": 5, "giugno": 6, "giu": 6, "luglio": 7, "lug": 7, "agosto": 8, "ago": 8, "settembre": 9, "set": 9, "ottobre": 10, "ott": 10, "novembre": 11, "nov": 11, "dicembre": 12, "dic": 12, "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "mai": 5, "juni": 6, "juli": 7, "oktober": 10, "dezember": 12, "janvier": 1, "janv": 1, "février": 2, "fevrier": 2, "févr": 2, "mars": 3, "avril": 4, "avr": 4, "juin": 6, "juillet": 7, "juil": 7, "août": 8, "aout": 8, "septembre": 9, "sept": 9, "octobre": 10, "décembre": 12, "decembre": 12, "januari": 1, "februari": 2, "maart": 3, "mei": 5, "augustus": 8, "december": 12, "enero": 1, "febrero": 2, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12, "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "maio": 5, "junho": 6, "julho": 7, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12, "january": 1, "jan": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "october": 10, "oct": 10, "november": 11}
GIORNI_SETTIMANA = {"lunedì": 0, "lunedi": 0, "montag": 0, "lundi": 0, "maandag": 0, "lunes": 0, "segunda-feira": 0, "segunda": 0, "monday": 0, "martedì": 1, "martedi": 1, "dienstag": 1, "mardi": 1, "dinsdag": 1, "martes": 1, "terça-feira": 1, "terça": 1, "terca-feira": 1, "tuesday": 1, "mercoledì": 2, "mercoledi": 2, "mittwoch": 2, "mercredi": 2, "woensdag": 2, "miércoles": 2, "miercoles": 2, "quarta-feira": 2, "quarta": 2, "wednesday": 2, "giovedì": 3, "giovedi": 3, "donnerstag": 3, "jeudi": 3, "donderdag": 3, "jueves": 3, "quinta-feira": 3, "quinta": 3, "thursday": 3, "venerdì": 4, "venerdi": 4, "freitag": 4, "vendredi": 4, "vrijdag": 4, "viernes": 4, "sexta-feira": 4, "sexta": 4, "friday": 4, "sabato": 5, "samstag": 5, "samedi": 5, "zaterdag": 5, "sábado": 5, "sabado": 5, "saturday": 5, "domenica": 6, "sonntag": 6, "dimanche": 6, "zondag": 6, "domingo": 6, "sunday": 6}
STOP_SECTIONS = ["notizie correlate", "related news", "related articles", "artigos relacionados", "noticias relacionadas", "articles liés", "ähnliche artikel", "weitere news", "meer nieuws", "関連記事", "notícias em destaque", "featured news"]
IGNORE_LINES = ["abbonamento", "iscriviti", "registrati", "accedi", "cookie", "privacy", "copyright", "newsletter", "smart tv", "playstation", "xbox", "iphone", "ipad", "registrieren", "anmelden", "kostenlos anmelden", "jetzt anmelden", "werbung", "s'inscrire", "se connecter", "registrarse", "iniciar sesión", "regista-te", "sign up", "log in", "subscribe", "download the app", "無料登録", "ログイン", "comentar", "seguir", "leggi anche", "descarga", "baixa a app", "bonne nouvelle", "freebox", "promoteur", "interview"]
PROMO_BAD_WORDS = ["black friday", "cyber monday", "sconto", "prezzi", "tariffe", "abbonamenti", "1 mês grátis", "um mês grátis", "30 dias grátis", "reclamações", "fidelização", "free trial", "risparmiare", "kündigen", "verlosung", "gewinnspiel", "freebox"]
FREE_KEYWORDS = ["gratis", "free", "gratuit", "kostenlos", "freemium", "em aberto", "en abierto", "grátis", "in chiaro", "senza abbonamento", "ohne abo", "無料", "フリーミアム", "app gratis"]
NEGATIVE_FREE_PHRASES = ["non è gratis", "non gratis", "nessuna diretta gratis", "keine kostenlose", "nicht kostenlos", "no es gratis", "solo a pagamento", "solo con abbonamento", "only with subscription", "abo nötig", "not free", "pay-tv"]

def classifica_sport(testo, canale_solo_sport=False):
    t = (testo or "").lower()
    if any(p in t for p in PAROLE_DA_ESCLUDERE):
        return None
    for sport, patterns in REGOLE_SPORT:
        if any(re.search(pat, t) for pat in patterns):
            return sport
    if canale_solo_sport and re.search(r"(\bx\b|vs\.?|×|対|\s-\s|\s·\s|\s@\s)", t):
        return "Altri Sport"
    return None

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
        self._pw = self._browser = self._context = None

    def _ensure_browser(self):
        if self._browser is None and sync_playwright is not None:
            try:
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
                self._context = self._browser.new_context(user_agent=HEADERS["User-Agent"], viewport={"width": 1366, "height": 768})
                self._context.add_cookies([
                    {"name": "CONSENT", "value": "YES+cb.20210328-17-p0.en+FX+999", "domain": ".google.com", "path": "/"},
                    {"name": "SOCS", "value": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9zUjMaAmVuIAEaBgiA_LyaBg", "domain": ".google.com", "path": "/"},
                ])
            except Exception:
                pass

    def close(self):
        for x in (self._context, self._browser, self._pw):
            try:
                if x:
                    x.close() if x != self._pw else x.stop()
            except Exception:
                pass

    @staticmethod
    def _is_blocked(html):
        if not html or len(html) < 700:
            return True
        low = html.lower()
        if ("access denied" in low and ("akamai" in low or "reference #" in low)) or "<title>access denied" in low or "just a moment..." in low or "cf-browser-verification" in low or "consent.google.com" in low:
            return True
        soup = BeautifulSoup(html, "html.parser")
        title_txt = (soup.title.get_text(strip=True) if soup.title else "").lower()
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        vis = len(soup.get_text(" ", strip=True))
        return vis < 300 or (title_txt == "dazn" and vis < 1200)

    def get_content(self, url, force_browser=False, allow_jina=True):
        if not force_browser and cffi_requests is not None:
            try:
                r = cffi_requests.get(url, impersonate="chrome", timeout=18, headers={"Accept-Language": HEADERS["Accept-Language"]})
                if r.status_code == 200 and not self._is_blocked(r.text):
                    return ("html", r.text, "cffi")
            except Exception:
                pass
        elif not force_browser:
            try:
                r = requests.get(url, headers=HEADERS, timeout=18)
                if r.status_code == 200 and not self._is_blocked(r.text):
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
                if not self._is_blocked(html):
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
                rj = requests.get(f"https://r.jina.ai/{url}", timeout=15, headers={"User-Agent": HEADERS["User-Agent"]})
                if rj.status_code == 200 and len(rj.text) > 500 and "Access Denied" not in rj.text[:500] and "Just a moment" not in rj.text[:500]:
                    return ("markdown", rj.text, "jina")
            except Exception:
                pass
        return (None, None, "blocked")

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
                                sport = classifica_sport(f"{title} {cats} {desc}", False)
                                if sport and title:
                                    nc, lk = matched_ids[cid]
                                    risultati.append({"data": dt.strftime("%Y-%m-%d"), "ora": dt.strftime("%H:%M"), "sport": sport, "competizione": cats.strip() or f"TV {paese}", "evento": title, "paese": paese, "canale": nc, "link": lk})
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
        sport = classifica_sport(f"{sez} {comp} {ev}", True)
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

def anno_vicino(m, g, ref):
    for y in (ref.year, ref.year + 1, ref.year - 1):
        try:
            if abs((datetime(y, m, g).date() - ref.date()).days) <= 180:
                return y
        except ValueError:
            pass
    return ref.year

def estrai_data(testo, ref=None, month_first=False):
    ref = ref or NOW
    t, low = (testo or "").strip(), (testo or "").strip().lower()
    if re.search(r"\b(oggi|heute|aujourd'hui|vandaag|hoy|hoje|today)\b", low) or "今日" in t or "本日" in t:
        return ref.date()
    if re.search(r"\b(domani|morgen|demain|mañana|amanhã|tomorrow)\b", low) or "明日" in t:
        return (ref + timedelta(days=1)).date()
    m = re.search(r"\b(\d{1,2})\.\s*(?:lun|mar|mi[ée]|jue|vie|s[áa]b|dom)\b", low)
    if m:
        dy = int(m.group(1))
        for d in range(-1, 10):
            if (ref + timedelta(days=d)).date().day == dy:
                return (ref + timedelta(days=d)).date()
    for pat, mode in [(r"\b(202\d)[-/.年](\d{1,2})[-/.月](\d{1,2})日?", "ymd"), (r"\b(\d{1,2})[/.](\d{1,2})[/.](202\d)\b", "dmy"), (r"(\d{1,2})月(\d{1,2})日", "jp")]:
        m = re.search(pat, t)
        if m:
            try:
                if mode == "ymd":
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
                if mode == "jp":
                    mo, dy = int(m.group(1)), int(m.group(2))
                    return datetime(anno_vicino(mo, dy, ref), mo, dy).date()
                a, b, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
                mo, dy = (a, b) if (month_first and a <= 12) or b > 12 else (b, a)
                return datetime(yr, mo, dy).date()
            except ValueError:
                pass
    mr = "|".join(sorted(MESI_MAP.keys(), key=len, reverse=True))
    m = re.search(rf"\b(\d{{1,2}})\.?\s*(?:de\s+)?({mr})\.?(?:\s*(?:de\s+)?(202\d))?\b", low)
    if m:
        try:
            dy, mo = int(m.group(1)), MESI_MAP[m.group(2)]
            return datetime(int(m.group(3)) if m.group(3) else anno_vicino(mo, dy, ref), mo, dy).date()
        except ValueError:
            pass
    m = re.search(rf"\b({mr})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(202\d))?\b", low)
    if m:
        try:
            mo, dy = MESI_MAP[m.group(1)], int(m.group(2))
            return datetime(int(m.group(3)) if m.group(3) else anno_vicino(mo, dy, ref), mo, dy).date()
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(?!\s*\d)", t)
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        try:
            dy, mo = int(m.group(1)), int(m.group(2))
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
    for gn, gi in GIORNI_SETTIMANA.items():
        if re.search(rf"\b{re.escape(gn)}\b", low):
            return (ref + timedelta(days=(gi - ref.weekday()) % 7)).date()
    return None

def estrai_ora(testo):
    tn = re.sub(r"\b(202\d)[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}[/.]\d{1,2}[/.]202\d\b|\b\d{1,2}\.\d{1,2}\.(?!\s*\d)|\b\d{1,2}/\d{1,2}\b", " ", (testo or "").strip())
    low = tn.lower()
    m = re.search(r"(\d{1,2})\s*時\s*(\d{2})?\s*分?", tn)
    if m:
        return int(m.group(1)), int(m.group(2) or "0")
    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", low)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or "0")
        if m.group(3) == "pm" and hh != 12:
            hh += 12
        elif m.group(3) == "am" and hh == 12:
            hh = 0
        return hh, mm
    for pat in [r"\b([01]?\d|2[0-9]):([0-5]\d)\b", r"\b([01]?\d|2[0-9])\s*h\s*([0-5]\d)?\b", r"\b([01]?\d|2[0-3])[.]([0-5]\d)\b", r"\b([01]?\d|2[0-3])\s*uhr\b", r"\b(?:ore|alle|às|as|à|a las)\s+([01]?\d|2[0-3])(?:[:.h]([0-5]\d))?\b"]:
        m = re.search(pat, low)
        if m:
            return int(m.group(1)), int(m.group(2) or "0") if m.lastindex and m.lastindex >= 2 else 0
    return None

def risolvi_tz(testo, default_tz):
    low = (testo or "").lower()
    if re.search(r"\b(bst|uk)\b", low): return ZoneInfo("Europe/London")
    if re.search(r"\b(gmt|utc)\b", low): return ZoneInfo("UTC")
    if re.search(r"\b(cet|cest|mez|mesz)\b", low): return ZoneInfo("Europe/Berlin")
    if re.search(r"\b(et|est|edt)\b", low): return ZoneInfo("America/Toronto")
    return ZoneInfo(default_tz)

def pulisci_ev(testo):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", testo or "").replace("**", "").replace("__", "")
    s = re.sub(r"^(?:#{1,6}\s+|[*•>\-]+\s+)", "", re.sub(r"\s+", " ", s)).strip(" -–—:|•·,")
    s = re.sub(r"^(?:esta|nesta|este|hoy|oggi|heute|today|this)\s+[^,]+,\s*", "", s, flags=re.I)
    s = re.sub(r"^(?:vê|ve|acompanha|assiste|guarda|mira|ver|watch|siehe|seht)\s+(?:em direto\s+)?(?:e\s+)?(?:grátis|gratis|for free|kostenlos|gratuitamente)\s+(?:o|a|os|as|lo|la|el)?\s*", "", s, flags=re.I)
    s = re.sub(r"^\d{1,2}[/.]\d{1,2}(?:[/.]202\d)?(?:\([日月火水木金土]\))?\s*[-–—,|•]*\s*", "", s)
    s = re.sub(r"^\d{1,2}月\d{1,2}日(?:\([日月火水木金土]\))?\s*[-–—,|•]*\s*", "", s)
    s = re.sub(r"^(?:ore|ab|às|as|à|um|kick-off)\s+", "", s, flags=re.I)
    s = re.sub(r"^\d{1,2}[:.h]\d{0,2}\s*(?:uhr|am|pm|et|est|cet|mez)?\s*[-–—:|•,]*\s*", "", s, flags=re.I)
    s = re.sub(r",?\s*(?:às|as|alle|à|a las|um|at)\s+\d{1,2}[:.h]?\d{0,2}\s*(?:uhr|am|pm)?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-–—|•]?\s*(?:dazn(?:\s+for\s+free|\s+freemium|\s+gratis|\s+app\s+gratis)?)$", "", s, flags=re.I)
    return s.strip(" -–—:|•·,.")

def valido_ev(testo, strict=False):
    if not testo or len(testo) < 5 or len(testo) > 125 or sum(c.isalpha() for c in testo) < 4:
        return False
    low = testo.lower()
    if any(b in low for b in IGNORE_LINES) or any(n in low for n in NEGATIVE_FREE_PHRASES):
        return False
    sfida = bool(re.search(r"(\s+-\s+|vs\.?|×|対|\s+x\s+|\s+@\s+|–|[A-Za-zÀ-ÿ]-[A-Za-zÀ-ÿ])", testo, re.I))
    if strict:
        return sfida
    return sfida or (classifica_sport(testo, False) is not None and 10 <= len(testo) <= 85)

def estrai_righe(soup):
    for br in soup.find_all("br"):
        br.replace_with("\n")
    out = []
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "div"]):
        if el.find(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "div"]):
            continue
        for s in el.get_text(" ").splitlines():
            c = re.sub(r"\s+", " ", s).strip()
            if c:
                out.append(c)
    return out

def estrai_dazn_contenuto(kind, content, cfg, is_cal=True, pub_dt=None, strict=False):
    ris, mf = [], cfg["tz"] in ("Asia/Tokyo", "America/Toronto")
    pt, maxd = "", None
    if kind == "html":
        soup = BeautifulSoup(content, "html.parser")
        pt = soup.title.get_text(" ", strip=True)[:30] if soup.title else ""
        injetta_alt_immagini(soup)
        ref = pub_dt.replace(tzinfo=None) if (pub_dt and abs((NOW.replace(tzinfo=None) - pub_dt.replace(tzinfo=None)).days) <= 21) else NOW.replace(tzinfo=None)
        for tr in soup.find_all("tr"):
            cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            if len(cells) >= 2 and (is_cal or any(k in " ".join(cells).lower() for k in ["dazn", "gratis", "free"])):
                rc = " | ".join(cells)
                d, hm = estrai_data(rc, ref, mf), estrai_ora(rc)
                if d and hm:
                    hh, mm = hm
                    try:
                        dt_it = (datetime(d.year, d.month, d.day, hh % 24, mm, tzinfo=risolvi_tz(rc, cfg["tz"])) + timedelta(days=hh // 24)).astimezone(ROME_TZ)
                        if MIN_DT <= dt_it <= MAX_DT:
                            ac = [c for c in cells if not (estrai_ora(c) and len(c) < 32) and not (re.match(r"^(dazn|gratis|free)", c, re.I) and len(c) < 25)]
                            ev = pulisci_ev(ac[next((i for i, x in enumerate(ac) if re.search(r"vs\.?| - | @ | x |×|対", x, re.I)), -1)]) if ac else ""
                            comp = (" • ".join(x for x in ac if pulisci_ev(x) != ev)[:55] or "DAZN Free") if len(ac) >= 2 else "DAZN Free"
                            if valido_ev(ev, strict):
                                ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(f"{comp} {ev}", True) or "Altri Sport", "competizione": comp, "evento": ev, "paese": cfg["paese"], "canale": cfg["canale"], "link": cfg["home"]})
                    except Exception:
                        pass
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        righe = estrai_righe(soup)
        tlen = sum(len(x) for x in righe)
    else:
        ref = pub_dt.replace(tzinfo=None) if (pub_dt and abs((NOW.replace(tzinfo=None) - pub_dt.replace(tzinfo=None)).days) <= 21) else NOW.replace(tzinfo=None)
        righe = [re.sub(r"\s+", " ", x).strip() for x in (content or "").splitlines() if x.strip()]
        tlen, pt = len(content or ""), "md"

    cd, hint, pdt = None, "", None
    for line in righe:
        lc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        lc = re.sub(r"^(?:#{1,6}\s+|[*•>\-]+\s+)", "", lc).replace("**", "").strip()
        if any(st in lc.lower() for st in STOP_SECTIONS):
            break
        frasi = re.split(r"(?<!\b\d)(?<!\b\d\d)(?<!\bvs)(?<!\bSt)(?<=[.!?])\s+(?=[A-ZÀ-ÿ0-9])", lc) if len(lc) > 140 else [lc]
        for fr in frasi:
            fr = fr.strip()
            low = fr.lower()
            if not fr or (any(b in low for b in IGNORE_LINES) and len(fr) < 95) or any(n in low for n in NEGATIVE_FREE_PHRASES):
                continue
            df, hm = estrai_data(fr, ref, mf), estrai_ora(fr)
            if df and (maxd is None or df > maxd):
                maxd = df
            if pdt and not hm and valido_ev(pulisci_ev(fr), strict):
                ev = pulisci_ev(fr)
                ris.append({"data": pdt.strftime("%Y-%m-%d"), "ora": pdt.strftime("%H:%M"), "sport": classifica_sport(ev, True) or "Altri Sport", "competizione": "DAZN Free", "evento": ev, "paese": cfg["paese"], "canale": cfg["canale"], "link": cfg["home"]})
                pdt = None
                continue
            pdt = None
            if df and not hm and len(fr) < 65:
                cd = df
                continue
            if not hm and re.search(r"(\s+-\s+|vs\.?|×|対|\s+x\s+|\s+@\s+)", fr, re.I) and len(fr) < 90:
                hint = pulisci_ev(fr)
                continue
            if not is_cal and "dazn" not in low:
                continue
            ed = df or cd
            if ed and hm:
                hh, mm = hm
                try:
                    dt_it = (datetime(ed.year, ed.month, ed.day, hh % 24, mm, tzinfo=risolvi_tz(fr, cfg["tz"])) + timedelta(days=hh // 24)).astimezone(ROME_TZ)
                except Exception:
                    continue
                if not (MIN_DT <= dt_it <= MAX_DT):
                    continue
                ev = pulisci_ev(fr)
                if not valido_ev(ev, strict):
                    if hint:
                        ev, hint = hint, ""
                    else:
                        pdt = dt_it
                        continue
                ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(ev, True) or "Altri Sport", "competizione": "DAZN Free", "evento": ev, "paese": cfg["paese"], "canale": cfg["canale"], "link": cfg["home"]})
    return ris, pt, tlen, (maxd.strftime("%m-%d") if maxd else "-")

def decodifica_gnews(url):
    if "news.google.com" not in url or _gnews_fn is None:
        return url
    try:
        res = _gnews_fn(url, interval=1)
        if res and (res.get("status") or res.get("success")) and res.get("decoded_url"):
            return res["decoded_url"]
    except Exception:
        pass
    return url

def cerca_gnews(q, hl, gl, ceid):
    out = []
    try:
        r = requests.get(f"https://news.google.com/rss/search?q={quote_plus(q)}&hl={hl}&gl={gl}&ceid={ceid}", headers=HEADERS, timeout=18)
        if r.status_code == 200 and "<item>" in r.text:
            for it in ET.fromstring(r.text).findall("./channel/item"):
                try:
                    pdt = parsedate_to_datetime(it.findtext("pubDate") or "").replace(tzinfo=None)
                except Exception:
                    pdt = None
                out.append(((it.findtext("title") or "").strip(), (it.findtext("link") or "").strip(), pdt))
    except Exception:
        pass
    return out

def scarica_giornali(fetcher, cfg, queries, direct=None, strict=True):
    ris, visti, cand = [], set(), [(cfg["paese"], u, None) for u in (direct or [])]
    visti.update(direct or [])
    gok = graw = 0
    for hl, gl, ceid, q in queries:
        for tit, ru, pdt in cerca_gnews(q, hl, gl, ceid):
            lt = tit.lower()
            if any(b in lt for b in PROMO_BAD_WORDS) or (pdt and (NOW.replace(tzinfo=None) - pdt).days > 21):
                continue
            if "dazn" in lt and any(k in lt for k in FREE_KEYWORDS):
                graw += 1
                if gok >= 5:
                    continue
                du = decodifica_gnews(ru)
                if "news.google.com" in du or any(s in du.lower() for s in SOCIAL_BLACKLIST):
                    continue
                gok += 1
                if du not in visti:
                    visti.add(du)
                    cand.append((tit, du, pdt))
    logs = []
    for tit, u, pdt in cand[:6]:
        k, c, via = fetcher.get_content(u, allow_jina=True)
        if not c:
            logs.append(f"{via}:0")
            continue
        ev, pt, tl, md = estrai_dazn_contenuto(k, c, cfg, True, pdt, strict)
        logs.append(f"{via}:{pt[:14]}({tl}c,m={md})->{len(ev)}")
        ris.extend(ev)
    return ris, gok, graw, logs

def scarica_dazn_italia(fetcher):
    cfg = {"paese": "DAZN Free Italia", "canale": "DAZN Free Italia", "tz": "Europe/Rome", "home": "https://www.dazn.com/it-IT/home"}
    print("🇮🇹⚡ Controllo DAZN Free Italia...")
    ris, dn_urls, wp_n = [], [], 0
    k, html, _ = fetcher.get_content("https://www.digital-news.it/news/dazn/", allow_jina=True)
    if html and k == "html":
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            href = urljoin("https://www.digital-news.it/", a["href"])
            la = (href + " " + a.get_text(" ", strip=True)).lower()
            if "dazn" in la and any(x in la for x in ["gratis", "free", "in chiaro", "gratuito", "freezone"]) and not any(b in la for b in PROMO_BAD_WORDS):
                if href not in dn_urls:
                    dn_urls.append(href)
    direct = ["https://www.goal.com/it/notizie/serie-b-in-tv-e-streaming-le-partite-gratis-e-in-chiaro-su-dazn/blt4d0df1681c08d377"] + dn_urls[:3]
    for site, q in [("https://www.pianetaserieb.it", "DAZN gratis"), ("https://www.seriebnews.com", "DAZN gratis"), ("https://www.mondomobileweb.it", "DAZN Free"), ("https://www.webnews.it", "DAZN gratis"), ("https://www.telefonino.net", "DAZN gratis")]:
        try:
            r = requests.get(f"{site}/wp-json/wp/v2/posts?search={quote_plus(q)}&per_page=3", headers=HEADERS, timeout=12)
            if r.status_code == 200:
                for p in r.json():
                    tit = BeautifulSoup(p.get("title", {}).get("rendered", ""), "html.parser").get_text()
                    if "dazn" in tit.lower() and any(x in tit.lower() for x in FREE_KEYWORDS) and not any(b in tit.lower() for b in PROMO_BAD_WORDS):
                        pdt = datetime.fromisoformat(p["date"][:19])
                        if (NOW.replace(tzinfo=None) - pdt).days <= 21:
                            ev, _, _, _ = estrai_dazn_contenuto("html", p.get("content", {}).get("rendered", ""), cfg, True, pdt, True)
                            wp_n += len(ev)
                            ris.extend(ev)
        except Exception:
            pass
    ev_g, gok, graw, logs = scarica_giornali(fetcher, cfg, [("it", "IT", "IT:it", '"DAZN" ("gratis" OR "in chiaro") ("Serie B" OR "volley" OR "LaLiga") -site:dazn.com'), ("it", "IT", "IT:it", '"DAZN" "senza abbonamento" partite OR calendario -site:dazn.com')], direct, True)
    ris.extend(ev_g)
    print(f"   🔎 [DAZN Free Italia] wp={wp_n}, gnews={gok}/{graw} | {' ; '.join(logs)} => TOT {len(ris)}")
    return ris

def scarica_dazn_spagna(fetcher):
    cfg = {"paese": "DAZN Free Spagna", "canale": "DAZN App Gratis (ES)", "tz": "Europe/Madrid", "home": "https://www.dazn.com/es-ES/home"}
    print("🇪🇸⚡ Controllo DAZN Free Spagna (MARCA, Mundo Deportivo)...")
    ris, vias = [], []
    for tag, url in [("marca", "https://www.marca.com/programacion-tv.html"), ("md-hoy", "https://www.mundodeportivo.com/guia-tv/futbol-hoy"), ("md-sem", "https://www.mundodeportivo.com/guia-tv/futbol-esta-semana"), ("md-bas", "https://www.mundodeportivo.com/guia-tv/baloncesto"), ("md-mot", "https://www.mundodeportivo.com/guia-tv/motor")]:
        k, c, via = fetcher.get_content(url, allow_jina=True)
        vias.append(f"{tag}:{via}")
        if not c:
            continue
        cd = NOW.date()
        if k == "html":
            soup = BeautifulSoup(c, "html.parser")
            injetta_alt_immagini(soup)
            viste = set()
            for el in soup.find_all(["tr", "li", "div", "h2", "h3", "caption"]):
                if el.name in ("h2", "h3", "caption"):
                    dh = estrai_data(el.get_text(" ", strip=True), NOW.replace(tzinfo=None))
                    if dh and len(el.get_text(" ", strip=True)) < 60:
                        cd = dh
                    continue
                if el.name == "div" and el.find(["tr", "li"]):
                    continue
                txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
                if not (12 <= len(txt) <= 420) or "dazn app gratis" not in txt.lower() or txt in viste:
                    continue
                viste.add(txt)
                dr, hm = estrai_data(txt, NOW.replace(tzinfo=None)) or cd, estrai_ora(txt)
                if hm:
                    try:
                        dt_it = datetime(dr.year, dr.month, dr.day, hm[0], hm[1], tzinfo=ZoneInfo("Europe/Madrid")).astimezone(ROME_TZ)
                        ev = pulisci_ev(re.sub(r"\bDAZN.*", "", txt, flags=re.I))
                        if MIN_DT <= dt_it <= MAX_DT and valido_ev(ev):
                            ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(ev, True) or "Calcio", "competizione": "DAZN Free Spagna", "evento": ev, "paese": cfg["paese"], "canale": cfg["canale"], "link": cfg["home"]})
                    except Exception:
                        pass
    ev_g, gok, graw, glogs = scarica_giornali(fetcher, cfg, [("es", "ES", "ES:es", '"DAZN App Gratis" OR "en abierto en DAZN" -site:dazn.com')], None, True)
    ris.extend(ev_g)
    print(f"   🔎 [DAZN Free Spagna] ({','.join(vias)}) gnews={gok}/{graw} => TOT {len(ris)}")
    return ris

def scarica_dazn_portogallo(fetcher):
    cfg = {"paese": "DAZN Free Portogallo", "canale": "DAZN Free Portogallo", "tz": "Europe/Lisbon", "home": "https://www.dazn.com/pt-PT/home"}
    print("🇵🇹⚡ Controllo DAZN Free Portogallo (Futebol365, OndeBola, ZeroZero, A Bola)...")
    ris, vias = [], []
    for tag, url in [("f365", "https://www.futebol365.pt/jogos-na-tv/"), ("ondebola", "https://ondebola.com/"), ("zerozero", "https://www.zerozero.pt/zapping.php")]:
        k, c, via = fetcher.get_content(url, allow_jina=True)
        vias.append(f"{tag}:{via}")
        if not c or k != "html":
            continue
        soup = BeautifulSoup(c, "html.parser")
        injetta_alt_immagini(soup)
        cd, viste = NOW.date(), set()
        for el in soup.find_all(["tr", "li", "div", "h2", "h3", "h4"]):
            if el.name in ("h2", "h3", "h4"):
                dh = estrai_data(el.get_text(" ", strip=True), NOW.replace(tzinfo=None))
                if dh and len(el.get_text(" ", strip=True)) < 60:
                    cd = dh
                continue
            if el.name == "div" and el.find(["tr", "li"]):
                continue
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if not (12 <= len(txt) <= 380) or txt in viste:
                continue
            if re.search(r"\bdazn\b[^0-9]{0,20}\b(gr[áa]tis|free|aberto|app)\b", txt.lower()):
                viste.add(txt)
                dr, hm = estrai_data(txt, NOW.replace(tzinfo=None)) or cd, estrai_ora(txt)
                if hm:
                    try:
                        dt_it = datetime(dr.year, dr.month, dr.day, hm[0], hm[1], tzinfo=ZoneInfo("Europe/Lisbon")).astimezone(ROME_TZ)
                        ev = pulisci_ev(re.sub(r"\bDAZN.*", "", txt, flags=re.I))
                        if MIN_DT <= dt_it <= MAX_DT and valido_ev(ev, True):
                            ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(ev, True) or "Calcio", "competizione": "DAZN Free Portogallo", "evento": ev, "paese": cfg["paese"], "canale": cfg["canale"], "link": cfg["home"]})
                    except Exception:
                        pass
    ev_g, gok, graw, glogs = scarica_giornali(fetcher, cfg, [("pt-PT", "PT", "PT:pt-150", '"DAZN" ("grátis" OR "em aberto") (site:abola.pt OR site:zerozero.pt OR site:record.pt OR site:ojogo.pt)')], None, True)
    ris.extend(ev_g)
    print(f"   🔎 [DAZN Free Portogallo] ({','.join(vias)}) gnews={gok}/{graw} | {' ; '.join(glogs)} => TOT {len(ris)}")
    return ris

def scarica_dazn_giappone(fetcher):
    cfg = {"paese": "DAZN Free Giappone", "canale": "DAZN Free Giappone", "tz": "Asia/Tokyo", "home": "https://www.dazn.com/ja-JP/home"}
    print("🇯🇵⚡ Controllo DAZN Free Giappone...")
    ris, gok, graw, logs = scarica_giornali(fetcher, cfg, [("ja", "JP", "JP:ja", '"DAZN Freemium" OR "DAZN 無料" (site:goal.com OR site:soccer-king.jp OR site:web.gekisaka.jp OR site:qoly.jp)')], ["https://www.goal.com/jp/lists/dazn-freemium-schedule/bltdc0f4d8734224b60"], True)
    print(f"   🔎 [DAZN Free Giappone] gnews={gok}/{graw} | {' ; '.join(logs)} => TOT {len(ris)}")
    return ris

def scarica_abema_giappone(fetcher):
    ris, urls, vias = [], ["https://www.soccer-king.jp/league/bundesliga"], []
    print("🇯🇵📺 Controllo ABEMA Free Giappone...")
    for _, ru, pdt in cerca_gnews('"ABEMA" "無料" ブンデスリーガ', "ja", "JP", "JP:ja"):
        if pdt and (NOW.replace(tzinfo=None) - pdt).days <= 14:
            u = decodifica_gnews(ru)
            if "news.google.com" not in u and u not in urls:
                urls.append(u)
            if len(urls) >= 4:
                break
    for u in urls:
        k, c, via = fetcher.get_content(u, allow_jina=True)
        vias.append(via)
        if not c or k != "html":
            continue
        soup = BeautifulSoup(c, "html.parser")
        injetta_alt_immagini(soup)
        for line in estrai_righe(soup):
            if "abema" in line.lower() and ("無料" in line or "vs" in line.lower() or "×" in line) and "abema de dazn" not in line.lower():
                d, hm = estrai_data(line, NOW.astimezone(JP_TZ).replace(tzinfo=None), True), estrai_ora(line)
                if d and hm:
                    hh, mm = hm
                    try:
                        dt_it = (datetime(d.year, d.month, d.day, hh % 24, mm, tzinfo=JP_TZ) + timedelta(days=hh // 24)).astimezone(ROME_TZ)
                        ev = pulisci_ev(re.sub(r"(?:ABEMA|無料配信|実況|解説).*", "", line))
                        if MIN_DT <= dt_it <= MAX_DT and valido_ev(ev, True):
                            ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(ev, True) or "Calcio", "competizione": "ABEMA Free Giappone", "evento": ev, "paese": "Giappone ABEMA Free", "canale": "ABEMA Free (JP)", "link": "https://abema.tv/video/genre/sports"})
                    except Exception:
                        pass
    print(f"   🔎 [ABEMA JP] ({','.join(vias)}) -> {len(ris)} eventi")
    return ris

def scarica_dazn_belgio(fetcher):
    cfg = {"paese": "DAZN Free Belgio", "canale": "DAZN Free Belgio", "tz": "Europe/Brussels", "home": "https://www.dazn.com/fr-BE/home"}
    print("🇧🇪⚡ Controllo DAZN Free Belgio (Voetbalkrant, Walfoot)...")
    ris, vias = [], []
    for tag, url in [("vk", "https://www.voetbalkrant.com/voetbal-op-tv"), ("wf", "https://www.walfoot.be/football-a-la-tv")]:
        k, c, via = fetcher.get_content(url, allow_jina=True)
        vias.append(f"{tag}:{via}")
        if not c or k != "html":
            continue
        soup = BeautifulSoup(c, "html.parser")
        injetta_alt_immagini(soup)
        cd = NOW.date()
        for el in soup.find_all(["tr", "li", "div", "h2", "h3"]):
            if el.name in ("h2", "h3"):
                dh = estrai_data(el.get_text(" ", strip=True), NOW.replace(tzinfo=None))
                if dh: cd = dh
                continue
            if el.name == "div" and el.find(["tr", "li"]):
                continue
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if len(txt) <= 350 and "dazn" in txt.lower() and any(x in txt.lower() for x in ["free", "freemium", "gratis", "gratuit"]):
                dr, hm = estrai_data(txt, NOW.replace(tzinfo=None)) or cd, estrai_ora(txt)
                if hm:
                    try:
                        dt_it = datetime(dr.year, dr.month, dr.day, hm[0], hm[1], tzinfo=ZoneInfo("Europe/Brussels")).astimezone(ROME_TZ)
                        ev = pulisci_ev(re.sub(r"\bDAZN.*", "", txt, flags=re.I))
                        if MIN_DT <= dt_it <= MAX_DT and valido_ev(ev, True):
                            ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(ev, True) or "Calcio", "competizione": "DAZN Free Belgio", "evento": ev, "paese": cfg["paese"], "canale": cfg["canale"], "link": cfg["home"]})
                    except Exception:
                        pass
    print(f"   🔎 [DAZN Free Belgio] ({','.join(vias)}) -> {len(ris)} eventi")
    return ris

def scarica_dazn_canada(fetcher):
    cfg = {"paese": "DAZN Free Canada", "canale": "DAZN Free Canada", "tz": "America/Toronto", "home": "https://www.dazn.com/en-CA/home"}
    print("🇨🇦⚡ Controllo DAZN Free Canada...")
    ris, gok, graw, logs = scarica_giornali(fetcher, cfg, [("en", "CA", "CA:en", '"DAZN" ("for free" OR "freemium") (NCAA OR NFL OR soccer OR boxing) -site:dazn.com')], None, True)
    print(f"   🔎 [DAZN Free Canada] gnews={gok}/{graw} | {' ; '.join(logs)} => TOT {len(ris)}")
    return ris

def scarica_dazn_germania_fussballgucken(fetcher):
    ris, vias = [], []
    print("🇩🇪⚡ Controllo FussballGucken.info (DAZN Germania)...")
    _, home_html, vh = fetcher.get_content("https://www.fussballgucken.info/", allow_jina=True)
    if not home_html:
        print(f"   🔎 [FussballGucken DE] home={vh} -> 0 eventi")
        return ris
    urls = {urljoin("https://www.fussballgucken.info/", a["href"]) for a in BeautifulSoup(home_html, "html.parser").find_all("a", href=True) if "free-tv" in (a["href"] + a.get_text()).lower()} or {"https://www.fussballgucken.info/free-tv"}
    for u in list(urls)[:3]:
        k, c, via = fetcher.get_content(u, allow_jina=True)
        vias.append(via)
        if not c:
            continue
        if k == "html":
            cs = BeautifulSoup(c, "html.parser")
            injetta_alt_immagini(cs)
            testo = cs.get_text("\n")
        else:
            testo = c
        lines = [re.sub(r"\s+", " ", x).strip() for x in testo.splitlines() if x.strip()]
        cd, i = NOW.date(), 0
        while i < len(lines):
            md = re.search(r"\b(\d{2}\.\d{2}\.202\d)\b", lines[i])
            if md and len(lines[i]) < 55:
                try: cd = datetime.strptime(md.group(1), "%d.%m.%Y").date()
                except Exception: pass
                i += 1
                continue
            mhm = re.match(r"^(\d{2}):(\d{2})(?:\s*Uhr)?\b", lines[i])
            if mhm:
                hh, mm, blocco, j = int(mhm.group(1)), int(mhm.group(2)), [], i + 1
                while j < len(lines) and j <= i + 18 and not re.match(r"^\d{2}:\d{2}(?:\s*Uhr)?\b", lines[j]) and not re.search(r"\b\d{2}\.\d{2}\.202\d\b", lines[j]):
                    blocco.append(lines[j])
                    j += 1
                if "dazn" in " | ".join(blocco).lower():
                    comp, ev = blocco[0] if blocco else "Calcio", ""
                    for idx, b in enumerate(blocco):
                        if b in ("·", "-", "vs", "vs.") and 0 < idx < len(blocco) - 1:
                            ev = f"{blocco[idx-1]} vs {blocco[idx+1]}"
                            break
                    if not ev:
                        ml = next((b for b in blocco if (" · " in b or " - " in b or " vs " in b.lower()) and "dazn" not in b.lower() and "sender" not in b.lower()), "")
                        ev = ml.replace(" · ", " vs ") if ml else ""
                    if not ev:
                        sq = [b for b in blocco[1:] if not any(w in b.lower() for w in ["spieltag", "dazn", "sender", "option", "free-tv", "live", "konferenz", "gruppe", "runde", "fifa+"]) and len(b) > 2]
                        ev = f"{sq[0]} vs {sq[1]}" if len(sq) >= 2 else (sq[0] if sq else "")
                    try:
                        dt_it = datetime(cd.year, cd.month, cd.day, hh, mm, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(ROME_TZ)
                        if MIN_DT <= dt_it <= MAX_DT and valido_ev(ev):
                            ris.append({"data": dt_it.strftime("%Y-%m-%d"), "ora": dt_it.strftime("%H:%M"), "sport": classifica_sport(f"{comp} {ev}", True) or "Calcio", "competizione": comp, "evento": ev, "paese": "DAZN Free Germania", "canale": "DAZN Free Germania", "link": "https://www.dazn.com/de-DE/home"})
                    except Exception:
                        pass
                i = j
                continue
            i += 1
    print(f"   🔎 [FussballGucken DE] ({','.join(vias)}) -> {len(ris)} eventi")
    return ris

def carica_manuali():
    if not os.path.exists("eventi_manuali.json"):
        return []
    try:
        with open("eventi_manuali.json", "r", encoding="utf-8") as f:
            return [ev for ev in json.load(f) if ev.get("data", "") >= NOW.strftime("%Y-%m-%d")]
    except Exception:
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
    tutti = scarica_epg_paesi() + scarica_futebol_tv_br() + scarica_auvaromaia_br() + scarica_gfesporte_br()
    fetcher = SmartFetcher()
    try:
        tutti += scarica_dazn_germania_fussballgucken(fetcher) + scarica_dazn_italia(fetcher) + scarica_dazn_spagna(fetcher) + scarica_dazn_portogallo(fetcher) + scarica_dazn_giappone(fetcher) + scarica_abema_giappone(fetcher) + scarica_dazn_belgio(fetcher) + scarica_dazn_canada(fetcher)
    finally:
        fetcher.close()
    finali = deduplica(tutti + carica_manuali())
    if finali:
        with open("eventi.json", "w", encoding="utf-8") as f:
            json.dump(finali, f, ensure_ascii=False, indent=2)
        with open("meta.json", "w", encoding="utf-8") as f:
            json.dump({"ultimo_aggiornamento": NOW.strftime("%d/%m/%Y alle %H:%M"), "totale_eventi": len(finali)}, f, ensure_ascii=False, indent=2)
        print(f"🎉 Salvati {len(finali)} eventi totali in eventi.json!")

if __name__ == "__main__":
    main()
