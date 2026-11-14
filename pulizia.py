"""Sistema quello che viene scritto o dettato nei campi: prezzi e indirizzi.

Qui non c'è nessun modello linguistico: sono regole scritte in Python, quindi
il risultato è sempre lo stesso e si può controllare con i test.

    leggi_prezzo("593€")     -> Decimal("593.00")
    sistema_prezzo("593€")   -> "€ 593,00"
    sistema_indirizzo("via ponte 33 Cernusco sul Naviglio milano")
                             -> "Via Ponte 33, Cernusco sul Naviglio, MI"

Quando una funzione non capisce il testo non tira a indovinare: leggi_prezzo
restituisce None, sistema_indirizzo si limita a mettere le maiuscole.
Il nome del cliente non passa da qui: resta esattamente come viene scritto.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from genera_preventivo import euro      # La funzione che scrive "€ 1.234,50": la riuso invece di riscriverla


# ---------------------------------------------------------------------------
# PREZZI
# ---------------------------------------------------------------------------
def _senza_migliaia(testo, separatore):
    """Toglie il separatore delle migliaia, controllando che sia messo bene: '1.200' -> '1200'.

    Dopo il primo gruppo ogni gruppo deve avere tre cifre. Se non è così
    ('1.2' oppure '12.34.5') restituisce None, cioè "non è scritto come migliaia".
    """
    gruppi = testo.split(separatore)                    # '1.200.000' -> ['1', '200', '000']
    primo_ok = 1 <= len(gruppi[0]) <= 3 and not gruppi[0].startswith("0")   # Il primo gruppo ha da 1 a 3 cifre e non comincia per zero ('0.500' non sono migliaia)
    if primo_ok and all(len(gruppo) == 3 for gruppo in gruppi[1:]):         # all(...) è True solo se la condizione vale per tutti i gruppi
        return "".join(gruppi)                          # Riattacca i gruppi senza separatore. Output: '1200000'
    return None


def leggi_prezzo(testo):
    """Capisce un prezzo scritto in tanti modi e lo restituisce come numero esatto.

    '593€', '€ 593', '593 euro', '593,5', '1.200', '1.200,50' vanno tutti bene.
    Se il testo non è un prezzo chiaro ('circa mille', '1,234') restituisce None.
    """
    if not isinstance(testo, str):
        return None
    pulito = testo.lower().replace("€", "").replace("euro", "").replace("eur", "")  # Toglie il simbolo e la parola: '593 Euro' -> '593 '
    pulito = re.sub(r"\s", "", pulito)                  # Toglie tutti gli spazi, anche in mezzo: '1 200' -> '1200'
    negativo = pulito.startswith("-")                   # Un meno davanti serve per gli sconti: '-150'
    pulito = pulito.lstrip("+-")                        # lstrip toglie quei caratteri solo dall'inizio
    if not re.fullmatch(r"[0-9.,]*[0-9][0-9.,]*", pulito):     # Devono restare solo cifre, punti e virgole, con almeno una cifra. Altrimenti non è un prezzo
        return None

    if "," in pulito and "." in pulito:
        # Ci sono tutti e due: quello che compare per ultimo separa i decimali, l'altro le migliaia.
        if pulito.rfind(",") > pulito.rfind("."):       # rfind dà la posizione dell'ultima volta che compare
            decimali_sep, migliaia_sep = ",", "."       # All'italiana: '1.200,50'
        else:
            decimali_sep, migliaia_sep = ".", ","       # All'inglese: '1,200.50'
        intero, _, decimali = pulito.rpartition(decimali_sep)   # Spezza in tre all'ultimo separatore: '1.200,50' -> ('1.200', ',', '50'). "_" è il pezzo che non serve
        intero = _senza_migliaia(intero, migliaia_sep)
    elif "," in pulito:
        intero, _, decimali = pulito.partition(",")     # In Italia la virgola separa i decimali: '593,5' -> ('593', ',', '5')
    elif "." in pulito:
        intero, decimali = _senza_migliaia(pulito, "."), ""     # Prima prova a leggerlo come migliaia: '1.200' -> '1200'
        if intero is None:
            intero, _, decimali = pulito.partition(".")         # Se non sono migliaia, il punto separa i decimali: '593.5'
    else:
        intero, decimali = pulito, ""                   # Nessun separatore: è un numero intero, '593'

    if intero is None or not intero.isdigit():          # isdigit è True se la stringa è fatta solo di cifre (e non è vuota)
        return None
    if decimali and (not decimali.isdigit() or len(decimali) > 2):  # I centesimi sono al massimo due cifre: '1,234' è ambiguo, meglio non indovinare
        return None

    prezzo = Decimal(intero + "." + (decimali or "0"))  # Ricompone il numero col punto, come lo vuole Decimal: '593' + '.' + '5'
    if negativo:
        prezzo = -prezzo
    return prezzo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)     # Sempre con due decimali. Output: Decimal('593.50')


def sistema_prezzo(testo):
    """'593€' -> '€ 593,00'. Se il testo non è un prezzo chiaro restituisce None."""
    prezzo = leggi_prezzo(testo)
    if prezzo is None:
        return None
    return euro(prezzo)


# ---------------------------------------------------------------------------
# INDIRIZZI
# ---------------------------------------------------------------------------
# Parole che in un indirizzo restano minuscole: "Cernusco sul Naviglio", "Via dei Mille".
# Gli articoli da soli (la, lo, il...) non ci sono, perché in mezzo a una via di solito
# fanno parte di un cognome: "Via La Pira".
PREPOSIZIONI = {
    "di", "del", "dello", "della", "dei", "degli", "delle",
    "a", "al", "allo", "alla", "ai", "agli", "alle",
    "da", "dal", "dallo", "dalla", "dai", "dagli", "dalle",
    "in", "nel", "nello", "nella", "nei", "negli", "nelle",
    "su", "sul", "sullo", "sulla", "sui", "sugli", "sulle",
    "con", "per", "tra", "fra", "e", "ed",
}
PREFISSI_MINUSCOLI = {"d", "de", "dell", "dall", "all", "nell", "sull"}     # La parte prima dell'apostrofo che resta minuscola: "Cassano d'Adda", "Trezzo sull'Adda"
NUMERO_ROMANO = re.compile(r"(?=[ivx]{2,})x{0,3}(ix|iv|v?i{0,3})")          # Da II a XXXIX: "XX Settembre", "IV Novembre", "Giovanni XXIII"
CIVICO = re.compile(r"\d+[a-z]?(bis|ter)?(/[\da-z]+)*", re.IGNORECASE)      # Un numero civico: 33, 33a, 12bis, 33/A, 6/8/10
CAP = re.compile(r"\d{5}")                                                  # Il codice postale: cinque cifre
MESI = {"gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"}
PAROLA_NUMERO = re.compile(r"\b(?:n|nr|numero|civico)\b[.°]*\s*(?=\d)", re.IGNORECASE)   # "n. 3", "n°3", "civico 3": la parola prima del numero, che si toglie
PAROLE_PROVINCIA = {"provincia", "prov"}                # "provincia di Milano": parole che annunciano la provincia, da togliere

# Le province italiane e la loro sigla. I nomi sono in minuscolo perché il
# confronto si fa in minuscolo. Per alcune c'è più di un modo di scriverle.
PROVINCE = {
    "agrigento": "AG", "alessandria": "AL", "ancona": "AN", "aosta": "AO", "arezzo": "AR",
    "ascoli piceno": "AP", "asti": "AT", "avellino": "AV", "bari": "BA",
    "barletta-andria-trani": "BT", "barletta andria trani": "BT", "barletta": "BT", "andria": "BT", "trani": "BT",
    "belluno": "BL", "benevento": "BN", "bergamo": "BG", "biella": "BI", "bologna": "BO",
    "bolzano": "BZ", "brescia": "BS", "brindisi": "BR", "cagliari": "CA", "caltanissetta": "CL",
    "campobasso": "CB", "caserta": "CE", "catania": "CT", "catanzaro": "CZ", "chieti": "CH",
    "como": "CO", "cosenza": "CS", "cremona": "CR", "crotone": "KR", "cuneo": "CN", "enna": "EN",
    "fermo": "FM", "ferrara": "FE", "firenze": "FI", "foggia": "FG",
    "forlì-cesena": "FC", "forlì cesena": "FC", "forli-cesena": "FC", "forli cesena": "FC", "forlì": "FC", "forli": "FC",
    "frosinone": "FR", "genova": "GE", "gorizia": "GO", "grosseto": "GR", "imperia": "IM",
    "isernia": "IS", "l'aquila": "AQ", "la spezia": "SP", "latina": "LT", "lecce": "LE",
    "lecco": "LC", "livorno": "LI", "lodi": "LO", "lucca": "LU", "macerata": "MC", "mantova": "MN",
    "massa-carrara": "MS", "massa carrara": "MS", "massa": "MS", "carrara": "MS",
    "matera": "MT", "messina": "ME", "milano": "MI", "modena": "MO",
    "monza e brianza": "MB", "monza e della brianza": "MB", "monza brianza": "MB", "monza-brianza": "MB", "monza": "MB",
    "napoli": "NA", "novara": "NO", "nuoro": "NU", "oristano": "OR", "padova": "PD", "palermo": "PA",
    "parma": "PR", "pavia": "PV", "perugia": "PG",
    "pesaro e urbino": "PU", "pesaro urbino": "PU", "pesaro-urbino": "PU", "pesaro": "PU", "urbino": "PU",
    "pescara": "PE", "piacenza": "PC", "pisa": "PI", "pistoia": "PT", "pordenone": "PN",
    "potenza": "PZ", "prato": "PO", "ragusa": "RG", "ravenna": "RA",
    "reggio calabria": "RC", "reggio di calabria": "RC", "reggio emilia": "RE", "reggio nell'emilia": "RE",
    "rieti": "RI", "rimini": "RN", "roma": "RM", "rovigo": "RO", "salerno": "SA", "sassari": "SS",
    "savona": "SV", "siena": "SI", "siracusa": "SR", "sondrio": "SO", "sud sardegna": "SU",
    "taranto": "TA", "teramo": "TE", "terni": "TR", "torino": "TO", "trapani": "TP", "trento": "TN",
    "treviso": "TV", "trieste": "TS", "udine": "UD", "varese": "VA", "venezia": "VE",
    "verbano-cusio-ossola": "VB", "verbano cusio ossola": "VB", "verbania": "VB",
    "vercelli": "VC", "verona": "VR", "vibo valentia": "VV", "vicenza": "VI", "viterbo": "VT",
}
SIGLE = set(PROVINCE.values())      # Solo le sigle, senza doppioni: {'MI', 'MB', 'BG', ...}


def _maiuscola(parola, prima):
    """Mette le maiuscole giuste a una parola. 'prima' è True se è la prima parola del pezzo."""
    minuscola = parola.lower()
    if parola[0].isdigit():
        return parola.upper().replace("BIS", "bis").replace("TER", "ter")   # Numeri civici e CAP: '33a' -> '33A', '12bis' resta '12bis', '20063' resta uguale
    if minuscola in ("bis", "ter"):
        return minuscola                                # '12 bis': resta minuscolo
    if "/" in parola:
        return parola                                   # Abbreviazioni con la barra ('s/N'): le lascio come sono scritte
    if not prima and minuscola in PREPOSIZIONI:
        return minuscola                                # 'SUL' -> 'sul'. La prima parola invece è sempre maiuscola: 'Al Ponte'
    if NUMERO_ROMANO.fullmatch(minuscola):
        return minuscola.upper()                        # 'xx' -> 'XX'
    if "'" in minuscola:
        inizio, _, resto = minuscola.partition("'")     # "d'adda" -> ('d', "'", 'adda')
        if not prima and inizio in PREFISSI_MINUSCOLI:
            return inizio + "'" + resto.capitalize()    # "d'Adda", "sull'Adda"
        return inizio.capitalize() + "'" + resto.capitalize()   # "Sant'Angelo", "L'Aquila"
    return "-".join(pezzo.capitalize() for pezzo in minuscola.split("-"))   # 'ponte' -> 'Ponte'; con il trattino ogni pezzo: 'forlì-cesena' -> 'Forlì-Cesena'


def _maiuscole(parole):
    """Sistema le maiuscole di una lista di parole e le riunisce: ['via', 'dei', 'mille'] -> 'Via dei Mille'."""
    return " ".join(_maiuscola(parola, numero == 0) for numero, parola in enumerate(parole))    # numero == 0 è True solo per la prima parola


def _posizione_civico(parole):
    """Trova dove sta il numero civico. Restituisce la sua posizione nella lista, oppure None.

    Il civico è l'ultimo numero che non sia un CAP e che non faccia parte di
    una data nel nome della via ('via 25 aprile 12': il civico è 12, non 25).
    """
    posizione = None
    for numero, parola in enumerate(parole):
        if numero == 0 or not CIVICO.fullmatch(parola):         # La prima parola è il tipo di via; fullmatch è True solo se tutta la parola ha la forma di un civico
            continue
        if CAP.fullmatch(parola):
            continue                                            # Cinque cifre: è il codice postale
        if numero + 1 < len(parole) and parole[numero + 1].lower() in MESI:
            continue                                            # Dopo c'è un mese: è una data ('25 aprile')
        posizione = numero                                      # Non mi fermo al primo: così alla fine resta l'ultimo trovato
    if posizione is not None and posizione + 1 < len(parole) and parole[posizione + 1].lower() in ("bis", "ter"):
        posizione += 1                                          # '12 bis': anche "bis" fa parte del civico
    return posizione


def _stacca_provincia(parole):
    """Separa il comune dalla provincia. Restituisce (parole del comune, sigla).

    ['Cernusco', 'sul', 'Naviglio', 'milano'] -> (['Cernusco', 'sul', 'Naviglio'], 'MI')
    Se la provincia non c'è, la sigla è una stringa vuota.
    """
    pulite = [parola.strip("()").lower() for parola in parole]  # Toglie le parentesi e mette in minuscolo: '(MI)' -> 'mi'
    for quante in (3, 2, 1):                                    # Prova prima i nomi lunghi ('monza e brianza'), poi quelli di una parola
        if len(parole) < quante:
            continue
        nome = " ".join(pulite[-quante:])                       # Le ultime 'quante' parole: [-1:] è l'ultima, [-2:] le ultime due
        sigla = PROVINCE.get(nome)                              # .get restituisce None se quel nome non è una provincia
        scritta_come_sigla = quante == 1 and nome.upper() in SIGLE      # L'ultima parola è già una sigla: 'mi', 'MB'
        if scritta_come_sigla:
            sigla = nome.upper()
        if sigla is None:
            continue
        comune = parole[:-quante]                               # Tutto quello che viene prima della provincia
        if not comune:
            if scritta_come_sigla:
                return [], sigla                                # 'via Roma 1 MI': c'è solo la sigla
            return parole, ""                                   # 'via Roma 1 milano': Milano qui è il comune, non la provincia
        if comune[-1].lower() in PREPOSIZIONI:
            return parole, ""                                   # 'Lido di Venezia': Venezia fa parte del nome del posto
        return comune, sigla
    return parole, ""


def sistema_indirizzo(testo):
    """Mette in ordine un indirizzo scritto di getto.

    'via ponte 33 Cernusco sul Naviglio milano' -> 'Via Ponte 33, Cernusco sul Naviglio, MI'

    Funziona quando c'è il numero civico oppure ci sono già le virgole. Se non
    riesce a capire dove finisce la via, sistema solo le maiuscole.
    """
    if not isinstance(testo, str) or not testo.strip():
        return ""
    testo = testo.replace("’", "'")                             # L'apostrofo "curvo" dei telefoni diventa quello normale
    testo = PAROLA_NUMERO.sub("", testo)                        # 'via Roma n. 3' -> 'via Roma 3'
    pezzi = [pezzo.split() for pezzo in testo.split(",") if pezzo.strip()]     # Divide alle virgole, poi ogni pezzo in parole: 'via Roma 1, milano' -> [['via', 'Roma', '1'], ['milano']]
    prima_parte = pezzi[0]
    dopo = [parola for pezzo in pezzi[1:] for parola in pezzo]  # Le parole di tutti i pezzi dopo la prima virgola, in una lista sola

    posizione = _posizione_civico(prima_parte)
    if posizione is not None:
        via = prima_parte[:posizione + 1]                       # Dall'inizio fino al civico compreso
        resto = prima_parte[posizione + 1:] + dopo              # Quello che viene dopo il civico: comune, provincia, CAP
    elif dopo and CIVICO.fullmatch(dopo[0]) and not CAP.fullmatch(dopo[0]):
        via, resto = prima_parte + dopo[:1], dopo[1:]           # 'via Ponte, 33, Cernusco': il civico è subito dopo la virgola, lo riattacco alla via
    elif dopo:
        via, resto = prima_parte, dopo                          # Niente civico, ma c'è una virgola che dice dove finisce la via
    else:
        return _maiuscole(prima_parte)                          # Né civico né virgole: non so dove finisce la via, sistemo solo le maiuscole

    # 'provincia di milano' -> 'milano': toglie "provincia" e il "di" che la segue
    resto = [parola for numero, parola in enumerate(resto)
             if parola.lower().rstrip(".") not in PAROLE_PROVINCIA
             and not (parola.lower() == "di" and numero > 0 and resto[numero - 1].lower().rstrip(".") in PAROLE_PROVINCIA)]

    cap = [parola for parola in resto if CAP.fullmatch(parola)][:1]     # Il codice postale, se c'è ([:1] tiene solo il primo)
    resto = [parola for parola in resto if not CAP.fullmatch(parola)]
    comune, sigla = _stacca_provincia(resto)

    risultato = [
        _maiuscole(via),                                        # 'Via Ponte 33'
        " ".join(cap + [_maiuscole(comune)]).strip(),           # '20063 Cernusco sul Naviglio' (il CAP solo se c'era)
        sigla,                                                  # 'MI'
    ]
    return ", ".join(pezzo for pezzo in risultato if pezzo)     # Unisce con le virgole solo i pezzi non vuoti
