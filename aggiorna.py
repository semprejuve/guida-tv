import gzip
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROME_TZ = ZoneInfo("Europe/Rome")
NOW = datetime.now(ROME_TZ)
MIN_DT = NOW - timedelta(hours=2)
MAX_DT = NOW + timedelta(days=7)

# ==============================================================================
# 1) QUI PUOI AGGIUNGERE FACILMENTE NUOVI PAESI E CANALI TV GRATUITI!
# Fonti XMLTV gratuite da epgshare01.online (puoi vedere tutti i file disponibili
# su: https://epgshare01.online/epgshare01/ )
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
    # 👉 ESEMPIO PER AGGIUNGERE ALTRI PAESI OGGI POMERIGGIO (basta togliere i # davanti!):
    # Codici utili su epgshare01: AT1 (Austria), FR1 (Francia), ES1 (Spagna), UK1 (Regno Unito), US2 (USA), AR1 (Argentina)
    # "Austria": {
    #     "epg_url": "https://epgshare01.online/epgshare01/epg_ripper_AT1.xml.gz",
    #     "canali": {
    #         "ORF 1": {"alias": ["orf 1", "orf eins", "orf 1 hd"], "link": "https://on.orf.at/"},
    #         "ORF Sport +": {"alias": ["orf sport +", "orf sport+", "orf sport plus"], "link": "https://on.orf.at/"},
    #         "ServusTV": {"alias": ["servustv", "servus tv", "servustv hd"], "link": "https://www.servustv.com/sport/"},
    #     },
    # },
}

# ==============================================================================
# 2) QUI PUOI AGGIUNGERE TUTTI I CANALI YOUTUBE CHE VUOI!
# ==============================================================================
CANALI_YOUTUBE = [
    {"nome": "CazéTV", "handle": "@CazeTV", "paese": "Brasile YouTube"},
    {"nome": "GE TV", "handle": "@getv", "paese": "Brasile YouTube"},
    {"nome": "Canal GOAT", "handle": "@canalgoatbr", "paese": "Brasile YouTube"},
    {"nome": "Xsports", "handle": "@xsports.brasil", "paese": "Brasile YouTube"},
    {"nome": "SportyNet", "handle": "@SportyNetBrasil", "paese": "Brasile YouTube"},
    {"nome": "N Sports", "handle": "@NSports", "paese": "Brasile YouTube"},
    {"nome": "Time Brasil", "handle": "@TimeBrasil", "paese": "Brasile YouTube"},
    {"nome": "NBA Brasil", "handle": "@nbabrasil", "paese": "Brasile YouTube"},
    {"nome": "SBT Sports", "handle": "@SBTSports", "paese": "Brasile YouTube"},
    {"nome": "Metrópoles Esportes", "handle": "@MetropolesEsportes", "paese": "Brasile YouTube"},
    {"nome": "Desimpedidos", "handle": "@desimpedidos", "paese": "Brasile YouTube"},
    {"nome": "Romário TV", "handle": "@RomarioTVoficial", "paese": "Brasile YouTube"},
    # 👉 Puoi aggiungere altri canali YouTube (anche di altri paesi!) copiando una riga qui sotto:
    # {"nome": "Nome Canale", "handle": "@NomeHandle", "paese": "Brasile YouTube"},
]

# ==============================================================================
# CLASSIFICATORE AUTOMATICO DEGLI SPORT
# ==============================================================================
PAROLE_DA_ESCLUDERE = [
    "telegiornale", "tg sport", "tg1", "tg2", "tg3", "sport mediaset",
    "sportmediaset", "tagesschau", "heute-journal", "meteo", "previsioni",
    "teleshopping", "rubrica", "cortes", "podcast", "resenha", "bom dia",
]

REGOLE_SPORT = [
    ("College Football", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b"]),
    ("Football Americano", [r"\bnfl\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bsuper bowl\b", r"\bran football\b"]),
    ("Formula 1", [r"\bformula 1\b", r"\bformula uno\b", r"\bformel 1\b", r"\bformule 1\b", r"\bf1\b", r"\bgran premio di f1\b"]),
    ("MotoGP", [r"\bmotogp\b", r"\bmoto gp\b", r"\bmoto2\b", r"\bmoto3\b", r"\bmotomondiale\b", r"\bsuperbike\b", r"\bwsbk\b"]),
    ("Sci Alpino", [r"\bsci alpino\b", r"\bski alpin\b", r"\bski weltcup\b", r"\bski-weltcup\b", r"\bslalom\b", r"\bdiscesa libera\b", r"\bsuper-g\b", r"\bsuper g\b", r"\briesenslalom\b", r"\babfahrt\b", r"\bcoppa del mondo di sci\b"]),
    ("Pallavolo", [r"\bpallavolo\b", r"\bvolley\b", r"\bvolleyball\b", r"\bvôlei\b", r"\bvolei\b", r"\bsuperlega\b", r"\bsuperliga\b", r"\blvf\b", r"\bvnl\b"]),
    ("Basket & NBA", [r"\bnba\b", r"\bwnba\b", r"\bbasket\b", r"\bpallacanestro\b", r"\bbasketball\b", r"\bbasquete\b", r"\beurolega\b", r"\beuroleague\b", r"\beurocup\b", r"\bnbb\b", r"\bfiba\b", r"\blega basket\b", r"\bbbl\b"]),
    ("Tennis", [r"\btennis\b", r"\btênis\b", r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bcoppa davis\b", r"\bdavis cup\b", r"\bbillie jean king\b", r"\broland garros\b", r"\bwimbledon\b", r"\baustralian open\b", r"\bus open\b", r"\bchallenger\b"]),
    ("Calcio", [
        r"\bcalcio\b", r"\bfutebol\b", r"\bfußball\b", r"\bfussball\b", r"\bserie a\b",
        r"\bserie b\b", r"\bsérie b\b", r"\bcoppa italia\b", r"\bsupercoppa\b",
        r"\bchampions league\b", r"\beuropa league\b", r"\bconference league\b",
        r"\bnations league\b", r"\bmondiali\b", r"\bpremier league\b", r"\bbundesliga\b",
        r"\bdfb-pokal\b", r"\bdfb pokal\b", r"\blaliga\b", r"\bla liga\b", r"\bligue 1\b",
        r"\bbrasileirão\b", r"\bbrasileirao\b", r"\bpaulistão\b", r"\bpaulistao\b",
        r"\bcarioca\b", r"\bcopa do brasil\b", r"\blibertadores\b", r"\bsul-americana\b",
        r"\bsudamericana\b", r"\bsuper league\b", r"\bchallenge league\b", r"\bcoppa svizzera\b",
        r"\bschweizer cup\b", r"\bsaudi pro league\b", r"\bmls\b", r"\bliga mx\b",
        r"\beredivisie\b", r"\bfa cup\b", r"\bcopa del rey\b", r"\bfutsal\b",
        r"\bfrauen-bundesliga\b", r"\bwomen's super league\b", r"\bwsl\b",
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
    # Sui canali YouTube 100% sportivi, titoli come "PALMEIRAS x FLAMENGO" sono quasi sempre calcio!
    if canale_solo_sport:
        if re.search(r"\b(x|vs\.?)\b", t):
            return "Calcio"
        if "ao vivo" in t or "live" in t:
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
        dt = datetime.strptime(s, "%Y%m%d%H%M%S %z")
        return dt.astimezone(ROME_TZ)
    except Exception:
        return None


def scarica_epg_paesi():
    risultati = []
    for paese, cfg in PAESI_TV.items():
        url = cfg["epg_url"]
        canali_cfg = cfg["canali"]
        alias_map = {}
        for nome_ufficiale, info in canali_cfg.items():
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
                        # Prova a riconoscere il canale dal nome visualizzato
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


def trova_video_renderers(obj):
    if isinstance(obj, dict):
        if "videoRenderer" in obj:
            yield obj["videoRenderer"]
        for v in obj.values():
            yield from trova_video_renderers(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from trova_video_renderers(item)


def scarica_youtube():
    risultati = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    cookies = {
        "CONSENT": "YES+cb.20210328-17-p0.en+FX+999",
        "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9zUjMaAmVuIAEaBgiA_LyaBg",
    }

    for ch in CANALI_YOUTUBE:
        nome = ch["nome"]
        handle = ch["handle"]
        paese = ch["paese"]
        url = f"https://www.youtube.com/{handle}/streams"
        print(f"▶️ Controllo YouTube {nome} ({handle})...")
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)
            resp.raise_for_status()
            idx = resp.text.find("var ytInitialData = ")
            if idx == -1:
                print(f"⚠️ Nessun dato trovato per {nome}")
                continue
            data, _ = json.JSONDecoder().raw_decode(resp.text, idx + len("var ytInitialData = "))
        except Exception as e:
            print(f"⚠️ Errore YouTube {nome}: {e}")
            continue

        trovati = 0
        visti_id = set()
        for vr in trova_video_renderers(data):
            vid = vr.get("videoId")
            if not vid or vid in visti_id:
                continue
            visti_id.add(vid)

            title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", [])) or vr.get("title", {}).get("simpleText", "")
            title = title.strip()
            if not title:
                continue

            # Controlla se è una diretta programmata futura
            up = vr.get("upcomingEventData")
            dt = None
            is_live_now = False

            if up and "startTime" in up:
                try:
                    dt = datetime.fromtimestamp(int(up["startTime"]), tz=ROME_TZ)
                except Exception:
                    dt = None
            else:
                # Controlla se è IN ONDA ADESSO (LIVE)
                overlays = vr.get("thumbnailOverlays", [])
                for ov in overlays:
                    st = ov.get("thumbnailOverlayTimeStatusRenderer", {}).get("style", "")
                    if st == "LIVE":
                        is_live_now = True
                for b in vr.get("badges", []):
                    st = b.get("metadataBadgeRenderer", {}).get("style", "")
                    lbl = b.get("metadataBadgeRenderer", {}).get("label", "").upper()
                    if "LIVE_NOW" in st or lbl in ("LIVE", "AO VIVO", "DAL VIVO"):
                        is_live_now = True
                if is_live_now:
                    dt = NOW

            if not dt or not (MIN_DT <= dt <= MAX_DT):
                continue

            sport = classifica_sport(title, canale_solo_sport=True)
            if not sport:
                continue

            titolo_finale = f"🔴 LIVE • {title}" if is_live_now else title
            risultati.append({
                "data": dt.strftime("%Y-%m-%d"),
                "ora": dt.strftime("%H:%M"),
                "sport": sport,
                "competizione": f"YouTube Diretta • {nome}",
                "evento": titolo_finale,
                "paese": paese,
                "canale": f"{nome} (YouTube)",
                "link": f"https://www.youtube.com/watch?v={vid}",
            })
            trovati += 1
        print(f"✅ {nome}: trovate {trovati} dirette in programma/live")
    return risultati


def scarica_dazn_free_italia():
    url = "https://www.dazn.com/it-IT/news/altro/come-funziona-la-modalita-free-su-dazn-e-come-attivarla/1n63xr4bv4gb8zw0uwdeq9cdq"
    print("⚡ Controllo pagina ufficiale DAZN Free Italia...")
    risultati = []
    try:
        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
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
        print(f"⚠️ DAZN Free Italia non raggiungibile automaticamente ({e}) - nessun problema, proseguo!")
    return risultati


def carica_manuali():
    if not os.path.exists("eventi_manuali.json"):
        return []
    try:
        with open("eventi_manuali.json", "r", encoding="utf-8") as f:
            dati = json.load(f)
        validi = []
        for ev in dati:
            if ev.get("data", "") >= NOW.strftime("%Y-%m-%d"):
                validi.append(ev)
        print(f"📝 Caricati {len(validi)} eventi da eventi_manuali.json")
        return validi
    except Exception as e:
        print(f"⚠️ Errore in eventi_manuali.json: {e}")
        return []


def deduplica(eventi):
    visti = set()
    puliti = []
    for ev in eventi:
        chiave = (
            ev.get("data", ""),
            ev.get("ora", ""),
            ev.get("canale", "").lower(),
            re.sub(r"[^a-z0-9]", "", ev.get("evento", "").lower())[:25],
        )
        if chiave not in visti:
            visti.add(chiave)
            puliti.append(ev)
    puliti.sort(key=lambda x: (x.get("data", ""), x.get("ora", ""), x.get("paese", "")))
    return puliti


def main():
    tutti = []
    tutti.extend(scarica_epg_paesi())
    tutti.extend(scarica_youtube())
    tutti.extend(scarica_dazn_free_italia())
    tutti.extend(carica_manuali())

    finali = deduplica(tutti)

    # Salva solo se ha trovato almeno qualcosa (evita di svuotare il sito in caso di blackout di rete)
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
        print("⚠️ Nessun evento raccolto in questa esecuzione, mantengo il vecchio eventi.json.")


if __name__ == "__main__":
    main()
