"""Corregge l'italiano delle descrizioni delle voci, chiedendolo a Gemini.

Tre regole di questo file:
1. A Gemini vanno SOLO i testi delle descrizioni. Mai clienti, indirizzi, prezzi.
2. Gemini propone, il codice controlla: una correzione che cambia un numero o
   allunga troppo il testo viene scartata, e resta il testo originale.
3. Se qualcosa va storto (chiave mancante, niente internet, limite superato)
   il preventivo si può creare lo stesso: la correzione è un aiuto, non un passaggio obbligato.

La chiave di Gemini sta nel file .env, che non finisce su GitHub:

    GEMINI_API_KEY=la-tua-chiave
"""

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
FILE_CHIAVE = CARTELLA / ".env"                         # Il file con la chiave. È elencato in .gitignore
MODELLO_PREDEFINITO = "gemini-3.5-flash-lite"           # Il modello più economico e veloce: per correggere l'ortografia basta. Si può cambiare dal file .env con GEMINI_MODELLO=...
INDIRIZZO = "https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent"
SECONDI_DI_ATTESA = 30                                  # Oltre questo tempo si smette di aspettare la risposta
MASSIMO_DESCRIZIONI = 80                                # Un preventivo vero ne ha qualche decina: di più è un errore
MASSIMO_CARATTERI = 20000                               # In tutto, sommando le descrizioni

# Quello che viene chiesto a Gemini. Le regole sono scritte per frenarlo: da solo tenderebbe a riscrivere tutto "in bella".
ISTRUZIONI = """Sei un correttore di bozze per un'impresa edile italiana.
Ricevi un elenco di descrizioni di lavori, scritte o dettate a voce da un artigiano che non è di madrelingua italiana.

Per ogni descrizione correggi SOLO:
- errori di ortografia, accenti e apostrofi;
- concordanze sbagliate (maschile/femminile, singolare/plurale) e preposizioni sbagliate;
- punteggiatura e spazi;
- parole ripetute per sbaglio (es. "colla colla");
- parole capite male dalla dettatura (es. "Acquafredda" al posto di "acqua fredda", "è" al posto di "e").

Regole da rispettare sempre:
- non aggiungere lavori, materiali, misure o dettagli che non sono scritti;
- non togliere nessun lavoro o materiale;
- non cambiare numeri, misure, marche e nomi di prodotti;
- non riscrivere le frasi e non cambiare lo stile: tieni le sue parole e il loro ordine ogni volta che sono corrette;
- se una descrizione è già corretta, restituiscila identica;
- se non capisci una parola, lasciala com'è;
- prima lettera maiuscola, nessun punto alla fine.

Rispondi SOLO con un elenco JSON di stringhe: una per ogni descrizione ricevuta, nello stesso ordine, senza altro testo.

Esempio di descrizioni ricevute:
["rimozione di pavimento in piastrelle , carico e trasporto al discarica autorizzato", "Posa piatto doccia"]
Esempio di risposta:
["Rimozione di pavimento in piastrelle, carico e trasporto alla discarica autorizzata", "Posa piatto doccia"]

Descrizioni da correggere:
"""


class ErroreCorrezione(Exception):
    """Un problema che impedisce la correzione. Il suo testo è una frase da mostrare a chi usa la pagina."""


# ---------------------------------------------------------------------------
# La chiave
# ---------------------------------------------------------------------------
def leggi_env(percorso):
    """Legge un file .env e restituisce un dizionario: 'GEMINI_API_KEY=abc' -> {"GEMINI_API_KEY": "abc"}.

    Se il file non esiste restituisce un dizionario vuoto. Le righe vuote e quelle che iniziano con # si saltano.
    """
    valori = {}
    if not percorso.exists():
        return valori
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        nome, _, valore = riga.partition("=")               # Spezza al primo "=": 'A=b=c' -> ('A', '=', 'b=c')
        valori[nome.strip()] = valore.strip().strip("\"'")  # Toglie spazi e virgolette intorno al valore: ' "abc" ' -> 'abc'
    return valori


def impostazioni():
    """Restituisce (chiave, modello). La chiave è "" se non è stata impostata.

    Guarda prima le variabili del computer (serviranno quando la pagina sarà online), poi il file .env.
    """
    dal_file = leggi_env(FILE_CHIAVE)
    chiave = os.environ.get("GEMINI_API_KEY") or dal_file.get("GEMINI_API_KEY") or ""
    modello = os.environ.get("GEMINI_MODELLO") or dal_file.get("GEMINI_MODELLO") or MODELLO_PREDEFINITO
    return chiave, modello


# ---------------------------------------------------------------------------
# Preparare la domanda e leggere la risposta.
# Queste funzioni non usano internet: si possono provare con i test.
# ---------------------------------------------------------------------------
def componi_richiesta(descrizioni):
    """Prepara quello che viene mandato a Gemini: le istruzioni seguite dall'elenco delle descrizioni.

    Restituisce un dizionario nella forma che vuole Gemini:
        {"contents": [{"parts": [{"text": "Sei un correttore... [\"Posa piato docia\"]"}]}]}
    Dentro ci sono solo le descrizioni: niente cliente, indirizzo o prezzi.
    """
    testo = ISTRUZIONI + json.dumps(descrizioni, ensure_ascii=False)     # json.dumps scrive la lista come testo: ["Posa piato docia", "..."]
    return {"contents": [{"parts": [{"text": testo}]}]}


def estrai_testo(risposta):
    """Tira fuori il testo scritto da Gemini dalla sua risposta.

    La risposta è fatta così: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
    Se ha un'altra forma (per esempio Gemini si è rifiutato di rispondere) lancia ErroreCorrezione.
    """
    try:
        parti = risposta["candidates"][0]["content"]["parts"]
        return "".join(parte.get("text", "") for parte in parti)     # Di solito la parte è una sola; se sono di più si uniscono
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ErroreCorrezione("Gemini ha risposto in un modo che non capisco. Riprova tra poco.")


def leggi_elenco(testo, quante):
    """Trasforma il testo di Gemini in una lista di stringhe: '["Posa piatto doccia"]' -> ["Posa piatto doccia"].

    'quante' è il numero di descrizioni mandate: la risposta deve averne altrettante,
    altrimenti non si saprebbe più quale correzione va con quale voce.
    """
    testo = testo.strip()
    testo = re.sub(r"^```(?:json)?\s*|\s*```$", "", testo)      # A volte la risposta arriva dentro un riquadro ```json ... ```: lo toglie
    try:
        elenco = json.loads(testo)
    except ValueError:
        raise ErroreCorrezione("Gemini ha risposto in un modo che non capisco. Riprova tra poco.")
    if not isinstance(elenco, list) or len(elenco) != quante or not all(isinstance(voce, str) for voce in elenco):
        raise ErroreCorrezione("Gemini ha risposto in un modo che non capisco. Riprova tra poco.")
    return elenco


def numeri(testo):
    """I numeri che compaiono in un testo, in ordine: 'Posa 2 porte da 80x210' -> ['2', '210', '80']."""
    return sorted(re.findall(r"\d+(?:[.,]\d+)?", testo))        # \d+ è un gruppo di cifre; (?:[.,]\d+)? prende anche i decimali, es. "2,5"


def accettabile(originale, corretta):
    """True se la correzione si può usare al posto dell'originale.

    Viene scartata se è vuota, se i numeri non sono più gli stessi (una misura cambiata è un errore grave),
    o se è molto più lunga o più corta: vuol dire che è stato aggiunto o tolto qualcosa.
    """
    if not corretta.strip():
        return False
    if numeri(originale) != numeri(corretta):
        return False
    lunga, corta = len(originale) * 1.4 + 15, len(originale) * 0.6 - 15     # Una correzione ortografica cambia poche lettere: resta dentro questi limiti
    return corta <= len(corretta) <= lunga


# ---------------------------------------------------------------------------
# La chiamata a Gemini: l'unica funzione che usa internet.
# ---------------------------------------------------------------------------
def chiedi_a_gemini(corpo, chiave, modello):
    """Manda la richiesta a Gemini e restituisce la sua risposta come dizionario.

    Ogni problema diventa un ErroreCorrezione con una frase comprensibile.
    """
    richiesta = urllib.request.Request(
        INDIRIZZO.format(modello=modello),
        data=json.dumps(corpo).encode("utf-8"),                 # Il dizionario diventa testo e poi byte, che è quello che viaggia in rete
        headers={"Content-Type": "application/json", "x-goog-api-key": chiave},     # La chiave va nell'intestazione, non nell'indirizzo: così non resta scritta nei registri
        method="POST",
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=SECONDI_DI_ATTESA) as risposta:
            return json.load(risposta)
    except urllib.error.HTTPError as errore:                    # Gemini ha risposto, ma con un codice di errore
        if errore.code == 429:
            raise ErroreCorrezione("Per ora il limite di richieste a Gemini è finito. Riprova tra qualche minuto.")
        if errore.code in (400, 401, 403):
            raise ErroreCorrezione("Gemini ha rifiutato la richiesta: controlla la chiave nel file .env.")
        if errore.code == 404:
            raise ErroreCorrezione(f'Gemini non conosce il modello "{modello}": va aggiornato il nome nel file .env.')
        raise ErroreCorrezione(f"Gemini ha un problema in questo momento (errore {errore.code}). Riprova tra poco.")
    except (urllib.error.URLError, TimeoutError) as errore:     # Non si è proprio arrivati a Gemini
        if isinstance(getattr(errore, "reason", None), ssl.SSLCertVerificationError):
            # Internet c'è, ma Python non riesce a controllare che dall'altra parte ci sia davvero Google.
            # Capita su Mac con Python scaricato da python.org: i certificati vanno installati una volta sola.
            raise ErroreCorrezione('Python non riesce a verificare il certificato di Google. Su Mac si risolve una volta sola aprendo "Install Certificates.command" nella cartella di Python in Applicazioni.')
        raise ErroreCorrezione("Non riesco a collegarmi a Gemini. Controlla la connessione a internet e riprova.")     # Niente internet, o risposta troppo lenta
    except ValueError:                                          # La risposta non è un JSON leggibile
        raise ErroreCorrezione("Gemini ha risposto in un modo che non capisco. Riprova tra poco.")


# ---------------------------------------------------------------------------
# La funzione che usa la pagina
# ---------------------------------------------------------------------------
def sistema_descrizioni(descrizioni, chiedi=chiedi_a_gemini):
    """Corregge un elenco di descrizioni. Restituisce una lista lunga uguale, con un dizionario per ognuna:

        {"testo": "Posa piatto doccia", "cambiata": True, "scartata": False}

    'testo' è il testo da usare. 'cambiata' dice se è diverso dall'originale.
    'scartata' è True quando Gemini aveva proposto una correzione ma il controllo l'ha rifiutata: resta l'originale.
    'chiedi' è la funzione che parla con Gemini: nei test se ne passa una finta, così non serve internet.
    """
    if len(descrizioni) > MASSIMO_DESCRIZIONI or sum(len(testo) for testo in descrizioni) > MASSIMO_CARATTERI:
        raise ErroreCorrezione("Ci sono troppe descrizioni, o sono troppo lunghe, per correggerle in una volta sola.")

    risultati = [{"testo": testo, "cambiata": False, "scartata": False} for testo in descrizioni]
    piene = [posizione for posizione, testo in enumerate(descrizioni) if testo.strip()]     # Le posizioni delle descrizioni non vuote: solo quelle vengono mandate
    if not piene:
        return risultati

    chiave, modello = impostazioni()
    if not chiave:
        raise ErroreCorrezione("La correzione del testo non è ancora attiva: manca la chiave di Gemini nel file .env.")

    da_mandare = [descrizioni[posizione].strip() for posizione in piene]
    risposta = chiedi(componi_richiesta(da_mandare), chiave, modello)
    corrette = leggi_elenco(estrai_testo(risposta), len(da_mandare))

    for posizione, originale, corretta in zip(piene, da_mandare, corrette):     # zip scorre le tre liste insieme: (0, "posa piato", "Posa piatto"), ...
        corretta = corretta.strip()
        if corretta == originale:
            continue                                            # Già giusta: resta com'è
        if accettabile(originale, corretta):
            risultati[posizione] = {"testo": corretta, "cambiata": True, "scartata": False}
        else:
            risultati[posizione]["scartata"] = True             # Correzione sospetta: si tiene il testo originale e lo si segnala
    return risultati
