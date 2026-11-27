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
    "meteo", "previsioni", "teleshopping", "quizshow", "reality", "blab",
    "bienvenue chez les",
]

TITLE_ONLY_EXCLUDE_REGEX = r"\b(?:notizie|notiziario|news|tg|rassegna\s+stampa|edizioni\s+del\s+tg)\b"

NON_SPORT_CATS_REGEX = (
    r"\b(?:film|movie|serie|s[ée]rie|jeunesse|animation|dessin\s*anim[ée]?|carton[ei]|bambini|ragazzi|kinder|"
    r"comedy|commedia|show|reality|intrattenimento|divertissement|unterhaltung|fiction|teatro|musica|"
    r"documentar\w*|doku[a-zäöüß-]*|talk\s*show|rubrica|reportage[a-zäöüß]*|notiziario|[a-zäöüß]*magazin[es]?)\b"
)

REPLAY_REGEX = (
    r"\(\s*[rw]\s*\)|\[\s*[rw]\s*\]|"
    r"\b(?:replic[ah]e?|in\s+replica|differita|in\s+differita|"
    r"wiederholung(?::\s*w)?|wdh\.?|wh\.?|rerun:\s*w|"
    r"rediffusion|rediff\.?|en\s+reprise|diff[ée]r[ée]|"
    r"repetici[óo]n|diferido|replay|re-?run|re-?live|relive|tape\s+delay|zeitversetzt|aufzeichnung|"
    r"partita\s+storica|partite\s+storiche|match\s+storico|archivio|amarcord|vintage|rewind|throwback|memory\s*-\s*rai)\b"
)

ESCLUDI_SPORT_REGEX = [
    r"\bcurling\b",
    r"\b(?:equitazione|ippica|horse racing|h[íi]pica|equestrian|pferdesport|pferderennen|reitsport|springreiten|dressur|galopp|show jumping|salto ostacoli)\b",
    r"\bp[áa]del\b",
    r"\b(?:scacchi|chess|ajedrez|schach|xadrez|[ée]checs)\b",
    r"\b(?:surf|surfing|shortboard|longboard|wsl|tsurigasaki|s\.one|s\.two)\b",
    r"\bkings?\s*(?:league|cup)\b",
    r"\b(?:boxe|boxing|boxeo|boxen|pugilato|bare\s*knuckle|bkfc|matchroom|queensberry)\b",
    r"\b(?:arti\s*marziali|artes\s*marciales|martial\s*arts|mma|ufc|muay\s*thai|kickboxing|bellator|pfl|one\s*championship|oktagon|rajadamnern|rws|kok\s*fight|efc|cage\s*warriors|karate|judo|taekwondo|wrestling|grappling)\b",
    r"\b(?:f1h2o|motonautica|supercars|gt\s+world\s+challenge)\b",
]

SECONDA_DIVISIONE_REGEX = (
    r"\b(?:"
    r"primavera(?:\s*[12])?|campionato\s+primavera|coppa\s+italia\s+primavera|"
    r"under\s*(?:23|21|20|19|18|17|16)|u-?(?:23|21|20|19|18|17|16)|youth\s*league|juniores|berretti|"
    r"serie\s*a2|lvf\s*a2|a2\s*(?:credem|maschile|femminile|\(m\)|\(f\))|"
    r"serie\s*a3|2\.?\s*bundesliga|zweite\s*bundesliga|3\.?\s*liga|dritte\s*liga|"
    r"segunda\s*divisi[óo]n|laliga\s*hypermotion|laliga\s*2|la\s*liga\s*2|primera\s*federaci[óo]n|"
    r"ligue\s*2|ligue\s*b|efl\s*championship|league\s*one|league\s*two|"
    r"challenge\s*league|challenger\s*pro\s*league|1b\s*pro\s*league|"
    r"eerste\s*divisie|keuken\s*kampioen|liga\s*portugal\s*2|segunda\s*liga|"
    r"superliga\s*b|superliga\s*2|liga\s+u|proa|prob|lnb\s*pro\s*b|2\.\s*basketball|"
    r"leb\s*oro|primera\s*feb|segunda\s*feb|"
    r"g[\s-]*league|del2|swiss\s*league|j[123]\s*league|\bj[123]\b|sv\.?\s*league|daido\s*life|"
    r"s[ée]rie\s*[cd]|serie\s*[cd]|série\s*b|"
    r"seconda\s*divisione|second\s*division|2a\s*divisione|2nd\s*division|divisi[óo]n\s*de\s*plata|"
    r"brasileir[ãa]o\s*(?:s[ée]rie\s*)?b|paulist[ãa]o\s*a2|paulista\s*a2|"
    r"campeonato\s+japon[êe]s|liga\s+japonesa|j-?league|b\.?\s*league"
    r")\b"
)

MAGAZINE_ALWAYS_REGEX = (
    r"[a-zäöüß]*magazin[es]?|"
    r"reportage[a-zäöüß]*|"
    r"\bdoku[a-zäöüß-]*|"
    r"\b(?:"
    r"matchnight|matchday\s+(?:live|show|highlights)|"
    r"rubrica|rotocalco|approfondimento|talk\s*show|podcast|cortes|resenha|mesa\s+redonda|debate|"
    r"domenica\s+sportiva|90[°º]?\s*minuto|novantesimo\s+minuto|pressing|dribbling|"
    r"tutti\s+convocati|fantacalcio|calciomercato|calcio\s*mercato|sportitalia\s*mercato|"
    r"sport\s*mediaset|sportmediaset|tg\s*sport|studio\s*sport|processo\s+del\s+luned[ìi]|"
    r"bordocampo|la\s+rosa\s+del\s+calcio|reparto\s+corse|oltre\s+la\s+rete|passaggi|sportabilia|"
    r"si\s+live\s*24|si\s+motori|si\s+cafe|inside\s+city|tutti\s+in\s+campo|diretta\s+stadio|lo\s+sai\s+che|prima\s+serata|"
    r"cartellino\s+rosa|otto\s+in\s+punto|speciale\s+cun|tg\s+betsson|"
    r"supertennis\s+(?:today|tg)|tennis\s+talk|tie\s+book|tie\s+movie|hawk\s+eye|circolando|race\s+to\s+foro|tennis\s+symposium|tutorial\s+pickleball|colpo\s+da\s+campione|"
    r"moviola|anteprima|prepartita|pre-?partita|postpartita|post-?partita|pre-?gara|post-?gara|vorbericht|analyse|"
    r"paddock|griglia\s+di\s+partenza|highlights|sintesi|i\s+gol\s+del|tutti\s+i\s+gol|zona\s+gol|"
    r"fuorigioco|tiki\s*taka|contropiede|"
    r"45\s*[-–—]\s*die\s+fu[ßs]{1,2}ball-halbzeit|fu[ßs]{1,2}ball-halbzeit|guten\s+abend\s+football|"
    r"zdfsportstudio\s+(?:uefa\s+)?champions\s+league|aktuelles?\s+sportstudio|"
    r"doppelpass|fantalk|sky90|bundesliga\s+pur|heimspiel|blickpunkt\s+sport|"
    r"alle\s+spiele,?\s+alle\s+tore|alle\s+tore|scooore|der\s+countdown|the\s+evolution\s+of\s+sport|the\s+power\s+of\s+sport|watts|"
    r"sportpanorama|sportflash|sportaktuell|adr[ée]naline|"
    r"zusammenfassung|r[üu]ckblick|vorschau|dokumentation|"
    r"[ée]mission|r[ée]sum[ée]|temps\s+forts|r[ée]trospective|avant-?match|apr[èe]s-?match|d[ée]brief|documentaire|"
    r"preview|review|watchalong|trending|rueda\s+de\s+prensa|press\s+conference|pesaje|weigh-?in|"
    r"documentary|docuseries|all\s+access|behind\s+the\s+scenes|paddock\s+abierto"
    r")\b"
)

MAGAZINE_NO_MATCH_REGEX = (
    r"[a-zäöüß]*sportstudio|"
    r"\b(?:"
    r"sportschau|champions\s+league\s+live|europa\s+league\s+live|conference\s+league\s+live|"
    r"speciale\s+(?:calcio|sport|serie|moto|f1|formula|volley|basket|tennis)|"
    r"focus\s+on|im\s+fokus|countdown|talk|studio|solo\s+calcio"
    r")\b"
)

CALCIO_FEMMINILE_REGEX = r"\b(?:femminil[ei]|feminino|feminina|femenin[ao]|f[ée]minin[eo]?|frauen|damen|women'?s?|woman|liga f|uwcl|wsl|nwsl|d1 arkema|frauenfu[ßs]ball)\b"

SWISS_LEAGUE_REGEX = r"\b(?:(?:brack\s+)?super\s+league|swiss\s+cup|schweizer\s+cup|coppa\s+svizzera|coupe\s+suisse)\b"
SWISS_CLUBS_REGEX = r"\b(?:servette|lausanne|basel|basilea|young\s+boys|lugano|luzern|lucerna|zurich|z[üu]rich|zurigo|st\.?\s*gallen|san\s+gallo|winterthur|sion|thun|thoune|grasshopper|yverdon|aarau|bellinzona|vaduz|xamax|stade\s+nyonnais)\b"
EURO_CUPS_REGEX = r"\b(?:champions\s+league|europa\s+league|conference\s+league|nations\s+league|mondiali|world\s+cup|europei|euro\s*202\d|amichevol[ei]|testspiel|friendly)\b"

REGOLE_SPORT = [
    ("College Football", [r"\bcollege football\b", r"\bncaa football\b", r"\bncaaf\b"]),
    ("Football Americano", [r"\bnfl\b", r"\bfoot us\b", r"\bfutebol americano\b", r"\bfootball americano\b", r"\bamerican football\b", r"\bfútbol americano\b", r"\bsuper bowl\b", r"\bran football\b", r"\bflag football\b", r"redzone", r"アメフト"]),
    ("Formula 1", [r"\bformula 1\b", r"\bf[óo]rmula 1\b", r"\bformula uno\b", r"\bformel 1\b", r"\bformule 1\b", r"\bf1\b", r"\bgran premio di f1\b", r"\bgarage f1\b"]),
    ("MotoGP", [r"\bmotogp\b", r"\bmoto gp\b", r"\bmoto2\b", r"\bmoto3\b", r"\bmotomondiale\b", r"\bsuperbike\b", r"\bwsbk\b"]),
    ("Snowboard", [r"\bsnowboard\b", r"\bsnowboardcross\b", r"\bboardercross\b"]),
    ("Sci Alpino", [r"\bsci alpino\b", r"\bski alpin\b", r"\bski weltcup\b", r"\bski-weltcup\b", r"\bslalom\b", r"\bdiscesa libera\b", r"\bsuper-g\b", r"\bsuper g\b", r"\briesenslalom\b", r"\babfahrt\b", r"\bcoppa del mondo di sci\b"]),
    ("Pallanuoto", [r"\bpallanuoto\b", r"\bwater\s*polo\b", r"\bwasserball\b", r"\bwaterpolo\b"]),
    ("Pallavolo", [r"\bpallavolo\b", r"\bvolley\b", r"\bvolleyball\b", r"\bv[ôo]lei\b", r"\bsuperlega\b", r"\bsuperliga\b", r"\blvf\b", r"\bvnl\b", r"\bserie a1\b", r"バレー"]),
    ("Basket & NBA", [r"\bnba\b", r"\bwnba\b", r"\bbasket\b", r"\bbasquete\b", r"\bbaloncesto\b", r"\bpallacanestro\b", r"\bbasketball\b", r"\bncaa\b", r"\bncaab\b", r"\beurolega\b", r"\beuroleague\b", r"\beurocup\b", r"\beuroliga\b", r"\bnbb\b", r"\bfiba\b", r"\blega basket\b", r"\bliga endesa\b", r"\bliga acb\b", r"\bliga betclic\b", r"\bmarch madness\b", r"\bbbl\b", r"バスケ", r"bリーグ"]),
    ("Tennis", [r"\btennis\b", r"\bt[êe]nis\b", r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bcoppa davis\b", r"\bdavis cup\b", r"\bbillie jean king\b", r"\broland garros\b", r"\bwimbledon\b", r"\baustralian open\b", r"\bus open\b", r"\bchallenger\b", r"テニス"]),
    ("Calcio", [r"\bcalcio\b", r"\bfutebol\b", r"\bf[úu]tbol\b", r"\bfootball\b", r"\bsoccer\b", r"\bfu[ßs]ball\b", r"\bvoetbal\b", r"\bserie a\b", r"\bserie b(?:kt)?\b", r"\bcoppa italia\b", r"\bsupercoppa\b", r"\bchampions league\b", r"\beuropa league\b", r"\bconference league\b", r"\bnations league\b", r"\bmondiali\b", r"\bpremier league\b", r"\bbundesliga\b", r"\bdfb-pokal\b", r"\bdfb pokal\b", r"\blaliga\b", r"\bla liga\b", r"\bligue 1\b", r"\bbrasileir[ãa]o\b", r"\bpaulist[ãa]o\b", r"\bcarioca\b", r"\bcopa do brasil\b", r"\blibertadores\b", r"\bsul-americana\b", r"\bsudamericana\b", r"\bjupiler\b", r"\bcroky cup\b", r"\bliga portugal\b", r"\bfa cup\b", r"\bcopa del rey\b", r"\bfutsal\b", r"\bfifa\b", r"サッカー", r"セリエa", r"ラリーガ", r"ブンデスリーガ", r"リーグアン", r"ベルギーリーグ"]),
]

WINTER_VENUES = [
    ("Bergisel", "Innsbruck"), ("Airdrenaline", "Innsbruck"), ("Tirol", "Innsbruck"),
    ("Innsbruck", "Innsbruck"), ("Killington", "Killington"), ("Copper Mountain", "Copper Mountain"),
    ("Beaver Creek", "Beaver Creek"), ("Tremblant", "Tremblant"), ("Gurgl", "Gurgl"),
    ("Sölden", "Sölden"), ("Levi", "Levi"), ("Val d'Isère", "Val d'Isère"),
    ("Courchevel", "Courchevel"), ("Val Gardena", "Val Gardena"), ("Alta Badia", "Alta Badia"),
    ("Madonna di Campiglio", "Madonna di Campiglio"), ("Bormio", "Bormio"), ("St. Moritz", "St. Moritz"),
    ("Adelboden", "Adelboden"), ("Wengen", "Wengen"), ("Kitzbühel", "Kitzbühel"),
    ("Schladming", "Schladming"), ("Garmisch", "Garmisch"), ("Cortina d'Ampezzo", "Cortina d'Ampezzo"),
    ("Cortina", "Cortina"), ("Kronplatz", "Kronplatz"), ("Zauchensee", "Zauchensee"),
    ("Tarvisio", "Tarvisio"), ("Kranjska Gora", "Kranjska Gora"), ("Flachau", "Flachau"),
    ("Lienz", "Lienz"), ("Semmering", "Semmering"), ("Åre", "Åre"), ("Kvitfjell", "Kvitfjell"),
    ("Soldeu", "Soldeu"), ("Crans-Montana", "Crans-Montana"), ("Saalbach", "Saalbach"),
    ("Sun Valley", "Sun Valley"), ("Chur", "Chur"), ("Secret Garden", "Secret Garden"),
    ("Mylin", "Mylin"), ("Carezza", "Carezza"), ("Davos", "Davos"), ("Bad Gastein", "Bad Gastein"),
    ("Scuol", "Scuol"), ("Rogla", "Rogla"), ("Bansko", "Bansko"), ("Sierra Nevada", "Sierra Nevada"),
    ("Laax", "Laax"), ("Calgary", "Calgary"), ("Aspen", "Aspen"), ("Veysonnaz", "Veysonnaz"),
    ("Mont-Sainte-Anne", "Mont-Sainte-Anne"), ("Cervinia", "Cervinia"), ("Zermatt", "Zermatt"),
    ("Klosters", "Klosters"), ("Lillehammer", "Lillehammer"), ("Ruka", "Ruka"),
    ("Kuusamo", "Kuusamo"), ("Kontiolahti", "Kontiolahti"),
]

MOTORS_VENUES = [
    (r"\bvalencian?[ao]?\b|\bricardo\s+tormo\b", "GP Valencia"),
    (r"\bqatar\b|\bkatar\b|\blusail\b|\blosail\b", "GP Qatar"),
    (r"\babu\s*dhabi\b|\byas\s*marina\b", "GP Abu Dhabi"),
    (r"\bportim[ãa]o\b|\bportugal\b|\bportogallo\b", "GP Portogallo"),
    (r"\bmisano\b|\bsan\s+marino\b", "GP San Marino"),
    (r"\bmugello\b", "GP Italia (Mugello)"),
    (r"\bmonza\b", "GP Italia (Monza)"),
    (r"\bimola\b", "GP Emilia-Romagna"),
    (r"\bsilverstone\b", "GP Gran Bretagna"),
    (r"\bcatalu[nñ]a\b|\bbarcell?ona\b|\bmontmel[óo]\b", "GP Catalogna"),
    (r"\bjerez\b", "GP Spagna (Jerez)"),
    (r"\bassen\b", "GP Olanda (Assen)"),
    (r"\bsachsenring\b", "GP Germania"),
    (r"\bspielberg\b|\bred\s+bull\s+ring\b", "GP Austria"),
    (r"\bmotegi\b|\bjapan\b|\bgiappone\b", "GP Giappone"),
    (r"\bphillip\s+island\b", "GP Australia"),
    (r"\bsepang\b|\bmalaysia\b", "GP Malesia"),
    (r"\bburiram\b|\bthailand\b", "GP Thailandia"),
    (r"\bmandalika\b|\bindonesia\b", "GP Indonesia"),
    (r"\baustin\b|\bamericas\b", "GP delle Americhe"),
    (r"\blas\s+vegas\b", "GP Las Vegas"),
    (r"\binterlagos\b|\bs[ãa]o\s+paulo\b|\bbrasil\b", "GP Brasile"),
    (r"\bmexico\b|\bmessico\b", "GP Messico"),
    (r"\bsuzuka\b", "GP Giappone (Suzuka)"),
    (r"\bmonaco\b|\bmontecarlo\b", "GP Monaco"),
    (r"\bspa[-\s]*francorchamps\b|\bbelgi\w+\b", "GP Belgio"),
    (r"\bzandvoort\b", "GP Olanda"),
    (r"\bhungaroring\b|\bungaria\b", "GP Ungheria"),
    (r"\bbaku\b|\bazerbaijan\b", "GP Azerbaijan"),
    (r"\bsingapore\b", "GP Singapore"),
    (r"\bbahrain\b|\bsakhir\b", "GP Bahrain"),
    (r"\bjeddah\b|\barabia\b", "GP Arabia Saudita"),
    (r"\bmelbourne\b|\baustralia\b", "GP Australia"),
    (r"\bshanghai\b|\bchina\b|\bcina\b", "GP Cina"),
    (r"\bmiami\b", "GP Miami"),
    (r"\bmontreal\b|\bcanada\b", "GP Canada"),
    (r"\bmadrid\b", "GP Spagna (Madrid)"),
]

COMP_PATTERNS = [
    (r"\b(?:coppa\s+davis|davis\s+cup)\b", "Coppa Davis"),
    (r"\bbillie\s+jean\s+king\b", "Billie Jean King Cup"),
    (r"\batp\s+finals\b", "ATP Finals"),
    (r"\bwta\s+finals\b", "WTA Finals"),
    (r"\baustralian\s+open\b", "Australian Open"),
    (r"\broland\s+garros\b", "Roland Garros"),
    (r"\bwimbledon\b", "Wimbledon"),
    (r"\bus\s+open\b", "US Open"),
    (r"\b(?:uefa\s+)?champions\s+league\b", "Champions League"),
    (r"\b(?:uefa\s+)?europa\s+league\b", "Europa League"),
    (r"\b(?:uefa\s+)?(?:europa\s+)?conf[eé]rence\s+(?:league|ligue)\b", "Conference League"),
    (r"\b(?:uefa\s+)?nations\s+league\b", "Nations League"),
    (r"\bserie\s*a1\s+(?:femminile|fineco|donne)\b", "Serie A1 Femminile"),
    (r"\bserie\s*a1\s+maschile\b", "Serie A1 Maschile"),
    (r"\bsuper\s*lega\b", "SuperLega Maschile"),
    (r"\bserie\s*b(?:kt)?\b", "Serie BKT"),
    (r"\bserie\s*a\b", "Serie A"),
    (r"\bcoppa\s+italia\b", "Coppa Italia"),
    (r"\bsupercoppa\b", "Supercoppa"),
    (r"\bbundesliga\b", "Bundesliga"),
    (r"\bdfb[-\s]*pokal\b", "DFB-Pokal"),
    (r"\bla\s*liga\b", "LaLiga"),
    (r"\bpremier\s+league\b", "Premier League"),
    (r"\bligue\s*1\b", "Ligue 1"),
    (r"\bformula\s*1\b|\bf1\b", "Formula 1"),
    (r"\bmotogp\b", "MotoGP"),
    (r"\bmoto2\b", "Moto2"),
    (r"\bmoto3\b", "Moto3"),
    (r"\bnfl\b", "NFL"),
    (r"\bnba\b", "NBA"),
    (r"\beurolega\b|\beuroleague\b", "Eurolega"),
    (r"\bcoppa\s+del\s+mondo\b|\bweltcup\b|\bcoupe\s+du\s+monde\b", "Coppa del Mondo"),
]


def ha_anno_passato(testo):
    for m in re.finditer(r"\b(201[5-9]|202[0-5])\b", testo or ""):
        yr = int(m.group(1))
        if yr < NOW.year - 1:
            return True
        if yr == NOW.year - 1:
            after = (testo or "")[m.end():m.end() + 6]
            if not re.match(r"^\s*[-/]\s*(?:26|2026)\b", after):
                return True
    return False


def estrai_match_da_testo(testo):
    s_raw = re.sub(r"\s+", " ", (testo or "")).strip()
    if not s_raw:
        return None

    team_pat = r"[A-ZÀ-ŸÄÖÜ][A-Za-zÀ-ÿäöüÄÖÜ0-9.'’/]{1,22}(?:\s+(?:di|del|della|dei|da|in|san|s\.|de|la|el|van|von|den|[A-ZÀ-ŸÄÖÜ0-9][A-Za-zÀ-ÿäöüÄÖÜ0-9.'’/]{0,20})){0,4}"
    sep_pat = r"(?:\s+(?:vs\.?|–|—|-|@|\bat\b|\bgegen\b|\bcontro\b)\s+|(?<![0-9a-zà-ÿ])-(?![0-9]))"
    bad_side = r"^\d+$|\b(?:coppa|davis|superlega|credem|banca|fineco|serie\s*a1?|champions|europa|conference|stagione|episode|ep|manche|lauf|spieltag|runde|round|singolare|doppio|qualifiche|prove|sprint|gara|giornata|pallavolo|pallanuoto|tennis|calcio|basket|diretta|live|rai|supertennis|202\d)\b"

    # Prova prima spezzando su ":" e "-" da destra verso sinistra (es. "Coppa Davis 2026 - Semifinale Italia - Cechia: 2° singolare")
    for frase in re.split(r"[.!?\n]+", s_raw):
        chunks = [c.strip() for c in frase.split(":") if c.strip()]
        for chunk in reversed(chunks):
            chunk_clean = re.sub(
                r"^(?:quarti(?:\s+di\s+finale)?|semifinal[ei]|final[ei]|ottavi|\d+[aª°]?\s*giornata|week\s*\d+|spieltag\s*\d+|thanksgiving\s+game|sunday\s+night|monday\s+night|thursday\s+night|diretta|live)\s*[-–—]?\s*",
                "",
                chunk,
                flags=re.I,
            ).strip()
            # Se ci sono più " - " (es. "Coppa Davis 2026 - Semifinale Italia - Cechia"), controlla gli ultimi due blocchi
            partes = re.split(r"\s+(?:vs\.?|–|—|-|@|\bat\b|\bgegen\b|\bcontro\b)\s+", chunk_clean, flags=re.I)
            if len(partes) >= 3:
                cand_a = re.sub(r"^(?:quarti(?:\s+di\s+finale)?|semifinal[ei]|final[ei]|ottavi|\d+[aª°]?\s*giornata)\s+", "", partes[-2].strip(), flags=re.I).strip()
                cand_b = partes[-1].strip()
                if not re.search(bad_side, cand_a, re.I) and not re.search(bad_side, cand_b, re.I) and 2 <= len(cand_a) <= 42 and 2 <= len(cand_b) <= 42:
                    return f"{cand_a} - {cand_b}"

            for m in re.finditer(rf"({team_pat}){sep_pat}({team_pat})", chunk_clean):
                a = re.sub(r"^(?:quarti(?:\s+di\s+finale)?|semifinal[ei]|final[ei]|ottavi|\d+[aª°]?\s*giornata)\s+", "", m.group(1).strip(" -–—:.,"), flags=re.I).strip()
                b = m.group(2).strip(" -–—:.,")
                if re.search(bad_side, a, re.I) or re.search(bad_side, b, re.I):
                    continue
                if 2 <= len(a) <= 42 and 2 <= len(b) <= 42 and a.lower() != b.lower():
                    return f"{a} - {b}"
    return None


def estrai_winter_dettagli(sport, full_text):
    t = full_text or ""
    low = t.lower()

    spec = ""
    if sport == "Snowboard":
        if re.search(r"\bbig\s*air\b", low): spec = "Big Air"
        elif re.search(r"\bslopestyle\b", low): spec = "Slopestyle"
        elif re.search(r"\bhalf[-\s]*pipe\b", low): spec = "Halfpipe"
        elif re.search(r"\b(?:snowboard\s*cross|boardercross|sbx)\b", low): spec = "Snowboard Cross"
        elif re.search(r"\bparallel[-\s]*(?:riesen)?slalom|pgs\b", low): spec = "Gigante Parallelo"
        elif re.search(r"\bslalom\b", low): spec = "Slalom Parallelo"
        else: spec = "Snowboard"
    else:
        if re.search(r"\b(?:riesenslalom|slalom\s+g[ée]ant|slalom\s+gigante|gigante)\b", low): spec = "Slalom Gigante"
        elif re.search(r"\bsuper[-\s]*g\b", low): spec = "Super-G"
        elif re.search(r"\b(?:discesa|abfahrt|descente|downhill)\b", low): spec = "Discesa Libera"
        elif re.search(r"\bslalom\b", low): spec = "Slalom"
        elif re.search(r"\bkombinat|combin\b", low): spec = "Combinata"
        else: spec = "Sci Alpino"

    gen = ""
    if re.search(r"\b(?:femminil[ei]|donne|frauen|damen|dames|femmes|women)\b", low):
        gen = "Donne"
    elif re.search(r"\b(?:maschil[ei]|uomini|m[äa]nner|herren|messieurs|hommes|men)\b", low):
        gen = "Uomini"

    manche = ""
    if re.search(r"\b(?:1\.?\s*(?:lauf|manche|durchgang)|1[aª]\s*manche|1[èe]re\s*manche)\b", low):
        manche = "(1ª Manche)"
    elif re.search(r"\b(?:2\.?\s*(?:lauf|manche|durchgang)|2[aª]\s*manche|2[èe]me\s*manche)\b", low):
        manche = "(2ª Manche)"
    elif re.search(r"\bqualif", low):
        manche = "(Qualificazioni)"

    luogo = ""
    for key, label in WINTER_VENUES:
        if re.search(rf"\b{re.escape(key)}\b", t, re.I):
            luogo = label
            break
    if not luogo:
        mv = re.search(r"\b(?:in|aus|da|dalle\s+nevi\s+di|from|à)\s+([A-ZÄÖÜÀ-Ÿ][A-Za-zÀ-ÿäöüÄÖÜ' -]{2,22})", t)
        if mv:
            cand = mv.group(1).strip(" .,:-/()")
            if not re.search(r"\b(?:diretta|live|eurosport|rai|srf|rts|rsi|weltcup|coppa|italia|mondo|diretta)\b", cand, re.I):
                luogo = cand

    comp = f"Coppa del Mondo • {luogo}" if luogo else "Coppa del Mondo"
    parti = [spec]
    if gen:
        parti.append(gen)
    if manche:
        parti.append(manche)
    ev = " ".join(parti)
    if luogo:
        ev = f"{ev} - {luogo}"
    return comp, ev


def estrai_motori_dettagli(sport, full_text):
    low = (full_text or "").lower()
    classe = sport
    if sport == "MotoGP":
        if re.search(r"\bmoto\s*3\b", low): classe = "Moto3"
        elif re.search(r"\bmoto\s*2\b", low): classe = "Moto2"
        elif re.search(r"\bsuperbike\b|\bwsbk\b", low): classe = "Superbike"

    sess = ""
    if re.search(r"\b(?:qualif|qp|q1|q2)\b", low): sess = "Qualifiche"
    elif re.search(r"\bsprint\b", low): sess = "Sprint"
    elif re.search(r"\b(?:gara|race|rennen|course|carrera)\b", low): sess = "Gara"
    elif re.search(r"\b(?:libere|practice|training|essai|ft[123]|fp[123])\b", low): sess = "Prove Libere"

    gp = ""
    for pat, label in MOTORS_VENUES:
        if re.search(pat, low):
            gp = label
            break

    comp = f"{classe} • {gp}" if gp else classe
    ev_parts = [classe]
    if sess:
        ev_parts.append(sess)
    ev = " - ".join(ev_parts)
    if gp:
        ev = f"{ev} ({gp})"
    return comp, ev


def arricchisci_epg(title, sub_title, desc, cats, sport, paese):
    t = (title or "").strip()
    st = (sub_title or "").strip()
    d = (desc or "").strip()
    all_info = f"{t} {st} {d}".strip()

    if sport in ("Sci Alpino", "Snowboard"):
        return estrai_winter_dettagli(sport, all_info)
    if sport in ("MotoGP", "Formula 1"):
        return estrai_motori_dettagli(sport, all_info)

    comp = ""
    for pat, label in COMP_PATTERNS:
        if re.search(pat, all_info, re.I):
            comp = label
            break
    if not comp:
        c_clean = (cats or "").strip()
        if c_clean and not re.match(r"^(?:sport|sports|altro|altri|evento|tv)$", c_clean, re.I):
            comp = c_clean
        else:
            comp = sport

    if sport in ("Pallavolo", "Pallanuoto") and comp == "Serie A":
        if re.search(r"\bfemminil[ei]|donne|fineco\b", all_info, re.I):
            comp = "Serie A1 Femminile"
        elif re.search(r"\bmaschil[ei]|uomini\b", all_info, re.I):
            comp = "Serie A1 Maschile"

    match_str = estrai_match_da_testo(t) or estrai_match_da_testo(st) or estrai_match_da_testo(d)
    if match_str:
        ev = f"NFL: {match_str}" if comp == "NFL" and "nfl" not in match_str.lower() else match_str
    elif st and len(st) >= 4 and st.lower() not in t.lower() and not re.match(r"^(?:sport|202\d|live|diretta)$", st, re.I):
        ev = f"{t}: {st}" if len(t) < 28 else st
    else:
        ev = t

    return comp, ev


def classifica_sport(title_text, full_text_for_checks, canale_solo_sport=False, paese=""):
    tl = (title_text or "").lower()
    t = (full_text_for_checks or title_text or "").lower()

    if any(p in t for p in PAROLE_DA_ESCLUDERE):
        return None
    if re.search(TITLE_ONLY_EXCLUDE_REGEX, tl):
        return None
    if re.search(REPLAY_REGEX, tl):
        return None
    if re.search(REPLAY_REGEX, t) and not re.search(r"\b(?:diretta|live)\b", tl):
        return None
    if ha_anno_passato(tl):
        return None
    if any(re.search(pat, t) for pat in ESCLUDI_SPORT_REGEX):
        return None
    if re.search(SECONDA_DIVISIONE_REGEX, t):
        return None

    is_match_or_race = bool(
        re.search(r"(\s+-\s+|\s+–\s+|\bvs\.?\b|×|\s+x\s+|\s+@\s+|\s+at\s+|\b(?:gran premio|grand prix|qualifiche|qualifying|gara|race|rennen|sprint|slalom|discesa|super-?g|gigante|semifinale|finale|quarti|ottavi)\b)", tl)
    )
    if re.search(MAGAZINE_ALWAYS_REGEX, tl) or (not is_match_or_race and (re.search(MAGAZINE_ALWAYS_REGEX, t) or re.search(MAGAZINE_NO_MATCH_REGEX, tl) or re.search(MAGAZINE_NO_MATCH_REGEX, t))):
        return None

    for sport, patterns in REGOLE_SPORT:
        if any(re.search(pat, tl) for pat in patterns):
            if sport == "Calcio":
                if re.search(CALCIO_FEMMINILE_REGEX, t):
                    return None
                if re.search(r"\bserie\s*b(?:kt)?\b", t):
                    if paese not in ("Italia", "DAZN Free Italia", "") or re.search(r"\b(?:brasil|brasileir|argentin|ecuador|colombia|chile|rugby|basket|volley|pallavolo)\b", t):
                        return None
                if paese == "Svizzera" and not re.search(EURO_CUPS_REGEX, t):
                    if re.search(SWISS_LEAGUE_REGEX, t) or re.search(SWISS_CLUBS_REGEX, t):
                        return None
            elif sport == "Pallavolo":
                if paese == "Brasile YouTube" and re.search(r"\b(?:feminin[ao]s?|superliga\s+f|mulheres|women)\b", t):
                    return None
                if re.search(r"\bserie\s*b(?:kt)?\b", t):
                    return None
            else:
                if re.search(r"\bserie\s*b(?:kt)?\b", t):
                    return None
            return sport

    if canale_solo_sport and re.search(r"(\bx\b|vs\.?|×|対|\s-\s|\s·\s|\s@\s)", tl):
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
                                sub_title = (elem.findtext("sub-title") or "").strip()
                                desc = (elem.findtext("desc") or "").strip()
                                cats = " ".join((c.text or "") for c in elem.findall("category"))
                                prev_shown = elem.find("previously-shown") is not None

                                if prev_shown or re.search(NON_SPORT_CATS_REGEX, cats.lower()):
                                    elem.clear()
                                    continue

                                nc, lk = matched_ids[cid]
                                full_title = f"{title} {sub_title} {cats}".strip()
                                full_text = f"{title} {sub_title} {cats} {desc}".strip()
                                low_head = f"{title} {sub_title} {desc[:250]}".lower()
                                has_live = bool(re.search(r"\b(?:diretta|live)\b", low_head))

                                if nc == "Eurosport 1 DE" and not has_live:
                                    elem.clear()
                                    continue

                                if nc == "SuperTennis":
                                    if not has_live or dt.hour < 9 or (re.search(r"\bep\.?\s*\d+\b", title.lower()) and not re.search(r"\b(?:diretta|live)\b", title.lower())):
                                        elem.clear()
                                        continue

                                if nc == "Rai Sport" and dt.hour < 13 and not has_live:
                                    elem.clear()
                                    continue

                                mins_day = dt.hour * 60 + dt.minute
                                if 30 <= mins_day < 510 and not has_live:
                                    if not re.search(r"\b(?:nfl|nba|ncaa|usa|canada|australia|giappone|tokyo|japan|china|cina|copper\s+mountain|killington|beaver\s+creek|aspen|qatar)\b", full_text.lower()):
                                        elem.clear()
                                        continue

                                sport = classifica_sport(full_title, full_text, False, paese=paese)
                                if sport and title:
                                    low_all = full_text.lower()

                                    if sport == "Calcio" and 0 <= dt.hour < 12 and not has_live:
                                        if not re.search(r"\b(?:argentin|boca|river|racing|independiente|san lorenzo|brasile|brasil|flamengo|palmeiras|botafogo|corinthians|sao paulo|libertadores|sudamericana|mls|messico|liga mx|concacaf|australia|a-league)\b", low_all):
                                            elem.clear()
                                            continue

                                    if nc in ("Sportitalia", "SoloCalcio") and sport == "Calcio":
                                        if re.search(r"\b(?:premier\s+league|champions\s+league|europa\s+league|conference\s+league|bundesliga|laliga|la\s+liga|ligue\s*1|eredivisie|serie\s+a|serie\s+b|coppa\s+italia|fa\s+cup|dfb)\b", low_all):
                                            elem.clear()
                                            continue

                                    comp, evento_finale = arricchisci_epg(title, sub_title, desc, cats, sport, paese)
                                    risultati.append({
                                        "data": dt.strftime("%Y-%m-%d"),
                                        "ora": dt.strftime("%H:%M"),
                                        "sport": sport,
                                        "competizione": comp,
                                        "evento": evento_finale,
                                        "paese": paese,
                                        "canale": nc,
                                        "link": lk,
                                    })
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
                if classifica_sport(f"futebol {comp} {ev}", f"futebol {comp} {ev}", True, paese="Brasile YouTube") != "Calcio":
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


def normalizza_sez_br(sez):
    s = (sez or "").lower()
    if "alem" in s: return "Bundesliga"
    if "espanh" in s or "laliga" in s: return "LaLiga"
    if "italian" in s: return "Serie A"
    if "franc" in s: return "Ligue 1"
    if "ingl" in s: return "Premier League"
    if "portug" in s: return "Liga Portugal"
    if "holand" in s: return "Eredivisie"
    return sez


def estrai_br_html(html, base_dt):
    ris, sez = [], ""
    for rl in BeautifulSoup(html, "html.parser").get_text("\n").splitlines():
        line = re.sub(r"\s+", " ", rl).strip()
        if not line:
            continue
        if len(line) < 55 and not re.match(r"^\d{1,2}h", line):
            if any(k in line.lower() for k in [
                "futebol", "campeonato", "eliminat", "copa ", "taça", "liga ", "vôlei", "volei",
                "basquete", "nba", "nbb", "futsal", "tênis", "automobilismo", "fórmula 1",
                "motogp", "nfl", "brasileirão", "laliga", "bundesliga", "premier league", "ligue 1",
            ]):
                sez = normalizza_sez_br(line)
            continue
        m = re.match(r"^(\d{1,2})h(\d{2})?\s*[–—\-]\s*(.+?)\s+[–—\-]\s+(.+)$", line)
        if not m:
            continue
        cf = risolvi_canali_br(m.group(4))
        if not cf:
            continue
        corpo = m.group(3).strip()
        comp, ev = ([x.strip() for x in corpo.split(":", 1)] if ":" in corpo else (sez or "Sport Brasile", corpo))
        mp = re.search(r"\(([^)]+)\)\s*$", ev)
        if mp and "youtube" not in mp.group(1).lower():
            if not comp or comp in ("Sport Brasile", "Bundesliga", "LaLiga", "Serie A", "Ligue 1", "Premier League"):
                comp = mp.group(1).strip()
            ev = re.sub(r"\s*\([^)]+\)\s*$", "", ev).strip()
        sport = classifica_sport(f"{sez} {comp} {ev}", f"{sez} {comp} {ev}", True, paese="Brasile YouTube")
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


def deduplica(eventi, manuali=None):
    manual_slots = {(m.get("data", ""), m.get("sport", ""), m.get("canale", "")) for m in (manuali or [])}
    visti, puliti = set(), []
    for ev in eventi:
        if ev not in (manuali or []) and (ev.get("data", ""), ev.get("sport", ""), ev.get("canale", "")) in manual_slots:
            continue
        tb = re.sub(r"\b(fc|sc|ec|cr|ca|sv|vfb)\b", "", ev.get("evento", "").split(":", 1)[-1].lower())
        k = (ev.get("data", ""), ev.get("ora", ""), ev.get("paese", ""), re.sub(r"[^a-z0-9]", "", tb)[:22])
        if k not in visti:
            visti.add(k)
            puliti.append(ev)
    puliti.sort(key=lambda x: (x.get("data", ""), x.get("ora", ""), x.get("paese", "")))
    return puliti


def main():
    manuali = carica_manuali()
    tutti = (
        scarica_epg_paesi()
        + scarica_futebol_tv_br()
        + scarica_auvaromaia_br()
        + scarica_gfesporte_br()
        + manuali
    )
    finali = deduplica(tutti, manuali)
    if finali:
        with open("eventi.json", "w", encoding="utf-8") as f:
            json.dump(finali, f, ensure_ascii=False, indent=2)
        with open("meta.json", "w", encoding="utf-8") as f:
            json.dump({"ultimo_aggiornamento": NOW.strftime("%d/%m/%Y alle %H:%M"), "totale_eventi": len(finali)}, f, ensure_ascii=False, indent=2)
        print(f"🎉 Salvati {len(finali)} eventi totali in eventi.json!")


if __name__ == "__main__":
    main()
