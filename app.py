"""La pagina per compilare un preventivo dal browser.

Si avvia dalla cartella del progetto con:

    python app.py

e si apre nel browser all'indirizzo http://127.0.0.1:8000

Come sono divisi i compiti:
- templates/pagina.html è quello che si vede: le caselle e i pulsanti.
- questo file riceve quello che è stato scritto nelle caselle, lo sistema con
  pulizia.py, lo controlla e crea il Word con genera_preventivo.py.
- correzione.py corregge l'italiano delle descrizioni chiedendolo a Gemini.
Tutte le regole (prezzi, indirizzi, conti, controlli) stanno in Python: la
pagina non fa calcoli, chiede a questo programma e mostra la risposta.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import unicodedata
from datetime import date, timedelta

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session

import correzione
import genera_preventivo as gp      # "as gp" è un soprannome: per usare euro() si scrive gp.euro()
from pulizia import leggi_prezzo, leggi_quantita, sistema_indirizzo, sistema_unita

CARTELLA_USCITA = gp.CARTELLA_USCITA                                # output/: dove finiscono i Word
CARTELLA_ARCHIVIO = gp.CARTELLA / "data" / "raw" / "preventivi"     # Dove si salvano i dati di ogni preventivo creato (resta solo sul Mac)

app = Flask(__name__)       # Crea il programma web. __name__ dice a Flask dove cercare la cartella templates/


# ---------------------------------------------------------------------------
# La password d'accesso.
# Quando la pagina sarà online chiunque potrà raggiungere il suo indirizzo: senza
# password potrebbe leggere i preventivi e consumare la chiave di Gemini.
# Regola: senza una password impostata la pagina non si apre affatto ("chiuso
# finché non è configurato"), così non può finire online aperta per dimenticanza.
# ---------------------------------------------------------------------------
LUNGHEZZA_MINIMA_PASSWORD = 8
TENTATIVI_MASSIMI = 8               # Password sbagliate consentite...
MINUTI_DI_BLOCCO = 10               # ...in questo numero di minuti. Poi bisogna aspettare
tentativi_sbagliati = []            # Gli orari delle ultime password sbagliate (in secondi, come li dà time.time())


def impostazione(nome):
    """Legge un'impostazione segreta: prima dalle variabili del computer (si usano online), poi dal file .env. "" se non c'è.

    Esempio: impostazione("PASSWORD_PAGINA") -> "quattro parole a caso"
    """
    return os.environ.get(nome) or correzione.leggi_env(correzione.FILE_CHIAVE).get(nome) or ""


def password_pagina():
    """La password scelta per entrare, oppure "" se manca o è troppo corta per essere sicura."""
    password = impostazione("PASSWORD_PAGINA")
    return password if len(password) >= LUNGHEZZA_MINIMA_PASSWORD else ""


def chiave_per_le_sessioni():
    """La chiave con cui Flask firma il "biglietto" che resta nel browser dopo essere entrati (la sessione).

    Se in .env c'è CHIAVE_SEGRETA usa quella. Altrimenti la ricava dalla password: così chi è entrato
    resta dentro anche quando il programma si riavvia, e cambiando password tutti devono rientrare.
    """
    segreta = impostazione("CHIAVE_SEGRETA")
    if segreta:
        return segreta
    if password_pagina():
        return hashlib.sha256(("preventivi-ai sessioni " + password_pagina()).encode("utf-8")).hexdigest()   # sha256 trasforma un testo in 64 caratteri da cui non si risale al testo
    return secrets.token_hex(32)    # Nessuna password: una chiave a caso, tanto non può entrare nessuno


app.secret_key = chiave_per_le_sessioni()
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),  # Dopo essere entrati si resta dentro 30 giorni dall'ultimo uso
    SESSION_COOKIE_HTTPONLY=True,                   # Il biglietto non è leggibile dal JavaScript della pagina
    SESSION_COOKIE_SAMESITE="Lax",                  # Un altro sito non può far partire richieste "a nome" di chi è entrato
    SESSION_COOKIE_SECURE=True,                     # Il biglietto viaggia solo su https. Sul proprio computer (http) viene spento in fondo al file
)


def troppi_tentativi():
    """True se negli ultimi dieci minuti ci sono state troppe password sbagliate."""
    limite = time.time() - MINUTI_DI_BLOCCO * 60
    tentativi_sbagliati[:] = [orario for orario in tentativi_sbagliati if orario > limite]   # Tiene solo i tentativi recenti. [:] modifica la lista esistente invece di crearne un'altra
    return len(tentativi_sbagliati) >= TENTATIVI_MASSIMI


@app.before_request
def controlla_accesso():
    """Gira prima di ogni richiesta: chi non è entrato con la password viene fermato qui.

    Se restituisce qualcosa, Flask manda quello e non esegue la funzione dell'indirizzo richiesto.
    """
    if request.endpoint in ("accesso", "static") or session.get("dentro"):
        return None                                 # Può passare
    if request.method == "GET":
        return redirect("/accesso")                 # Chi apre la pagina viene mandato a scrivere la password
    return jsonify({"errore": "Devi rientrare con la password.", "accesso": True}), 401     # 401 = "non hai il permesso": lo ricevono i pulsanti della pagina se la sessione è scaduta


@app.route("/accesso", methods=["GET", "POST"])
def accesso():
    """La pagina dove si scrive la password."""
    if not password_pagina():
        return render_template("accesso.html", manca=True, minima=LUNGHEZZA_MINIMA_PASSWORD), 503
    if request.method == "POST":
        if troppi_tentativi():
            return render_template("accesso.html", errore=f"Troppi tentativi sbagliati. Aspetta {MINUTI_DI_BLOCCO} minuti e riprova."), 429
        scritta = request.form.get("password", "")
        if hmac.compare_digest(scritta.encode("utf-8"), password_pagina().encode("utf-8")):    # compare_digest confronta in un tempo sempre uguale: dal tempo di risposta non si capisce quante lettere erano giuste
            session["dentro"] = True
            session.permanent = True                # "permanent" = dura i 30 giorni scritti sopra, non solo finché il browser resta aperto
            return redirect("/")
        tentativi_sbagliati.append(time.time())
        return render_template("accesso.html", errore="Password sbagliata."), 401
    return render_template("accesso.html")


@app.route("/esci")
def esci():
    """Butta via il biglietto: per rientrare servirà di nuovo la password."""
    session.clear()
    return redirect("/accesso")


def leggi_impresa():
    """I dati dell'impresa da mettere nel Word. Restituisce (impresa, e_di_esempio).

    Li cerca in tre posti, in ordine:
    1. la variabile IMPRESA_JSON (servirà online, dove la cartella data/raw non esiste);
    2. il file data/raw/impresa.json (sul proprio computer);
    3. l'esempio inventato: in questo caso e_di_esempio è True, e la pagina avvisa.
    """
    testo = os.environ.get("IMPRESA_JSON")
    if testo:
        try:
            return json.loads(testo), False
        except ValueError:
            return None, False                      # Scritta male: controlla_impresa lo dirà con una frase
    if gp.IMPRESA_VERA.exists():
        return gp.leggi_json(gp.IMPRESA_VERA), False
    return gp.leggi_json(gp.IMPRESA_ESEMPIO), True


# ---------------------------------------------------------------------------
# Dal modulo della pagina ai dati del preventivo.
# Queste funzioni non sanno niente di pagine web: prendono dizionari e
# restituiscono dizionari, quindi si possono provare con i test.
# ---------------------------------------------------------------------------
def numero_per_json(numero):
    """Trasforma un Decimal in un numero normale, come lo vuole il file JSON: Decimal('700.00') -> 700, Decimal('8.50') -> 8.5."""
    if numero == int(numero):
        return int(numero)
    return float(numero)


# Come si dice "il prezzo per ogni ..." con ogni unità: "al mq", "all'ora", "al pezzo"...
FRASI_PER_UNITA = {
    "mq": "al mq", "mt": "al mt", "ml": "al ml", "mc": "al mc", "kg": "al kg",
    "pz": "al pezzo", "ore": "all'ora", "giorni": "al giorno",
}


def frase_per_unita(unita):
    """'mq' -> 'al mq', 'ore' -> "all'ora", '' -> 'per unità'.

    Scrivere sempre "al {unita}" darebbe "al ore" o "al unità". Per le unità che non conosco
    la frase resta corretta in ogni caso: 'fusti' -> 'per unità (fusti)'.
    """
    if not unita:
        return "per unità"
    return FRASI_PER_UNITA.get(unita) or f"per unità ({unita})"


def leggi_voce(numero, dati):
    """Trasforma una voce scritta nella pagina in una voce del preventivo.

    'dati' è un dizionario con i testi delle caselle, per esempio:
        {"descrizione": "Rasatura", "misura": "misura", "quantita": "25",
         "unita": "mq", "prezzo": "700€", "tipo_prezzo": "totale"}
    Restituisce (voce, problemi). La voce è None se la riga è stata lasciata vuota.
    I problemi sono frasi su quello che non è stato capito, es. un prezzo scritto in modo strano.
    """
    if not isinstance(dati, dict):      # Un dato che non è un insieme di caselle: lo salto invece di andare in errore
        return None, []
    a_misura = dati.get("misura") == "misura"
    testo = {campo: str(dati.get(campo) or "").strip() for campo in ("descrizione", "quantita", "unita", "prezzo")}     # I testi delle caselle senza spazi intorno; una casella mancante diventa ""
    if not a_misura:
        testo["quantita"] = testo["unita"] = ""     # Quantità e unità sono nascoste nelle voci a corpo: se c'è qualcosa di scritto è un residuo, non va contato
    if not any(testo.values()):         # any(...) è True se almeno una casella contiene qualcosa
        return None, []                 # Riga lasciata tutta vuota: si salta

    voce, problemi = {"descrizione": testo["descrizione"]}, []

    prezzo = None
    if testo["prezzo"]:
        prezzo = leggi_prezzo(testo["prezzo"])
        if prezzo is None:
            problemi.append(f'Voce {numero}: non ho capito il prezzo "{testo["prezzo"]}". Scrivilo come 593 oppure 593,50')

    if a_misura:
        # Voce a misura: servono quantità e unità, e il prezzo può essere il totale oppure quello per unità.
        if testo["unita"]:
            voce["unita"] = sistema_unita(testo["unita"])   # "Metri Quadrati" -> "mq"
        if testo["quantita"]:
            quantita = leggi_quantita(testo["quantita"])    # Come leggi_prezzo ma con tre decimali: capisce "8,5", "25" e "2,125"
            if quantita is None:
                problemi.append(f'Voce {numero}: non ho capito la quantità "{testo["quantita"]}". Scrivila come 25 oppure 8,5')
            else:
                voce["quantita"] = numero_per_json(quantita)
        if prezzo is not None:
            campo = "importo" if dati.get("tipo_prezzo") == "totale" else "prezzo_unitario"    # Il prezzo scritto è per tutta la voce oppure per ogni mq?
            voce[campo] = numero_per_json(prezzo)
    elif prezzo is not None:
        voce["importo"] = numero_per_json(prezzo)           # Voce a corpo: il prezzo è l'importo della voce

    return voce, problemi


def leggi_modulo(dati):
    """Trasforma tutto il modulo della pagina in un preventivo. Restituisce (preventivo, problemi).

    Il nome del cliente resta esattamente come è stato scritto. L'indirizzo
    passa da sistema_indirizzo, i prezzi da leggi_prezzo.
    """
    if not isinstance(dati, dict):      # La pagina manda sempre un dizionario, ma una richiesta storta non deve mandare in crash il programma
        dati = {}
    preventivo = {
        "tipo": dati.get("tipo") or "preventivo",
        "cliente": str(dati.get("cliente") or "").strip(),
        "indirizzo": sistema_indirizzo(str(dati.get("indirizzo") or "")),
        "titolo": str(dati.get("titolo") or "").strip(),
        "data": str(dati.get("data") or "").strip(),
        "voci": [],
    }
    problemi = []
    elenco_voci = dati.get("voci")
    for dati_voce in elenco_voci if isinstance(elenco_voci, list) else []:      # Se "voci" non è una lista (es. un testo) si fa finta che sia vuota
        voce, problemi_voce = leggi_voce(len(preventivo["voci"]) + 1, dati_voce)    # Il numero della voce è la sua posizione tra quelle non vuote
        if voce is not None:
            preventivo["voci"].append(voce)
            problemi += problemi_voce
    return preventivo, problemi


def riassunto(preventivo, problemi):
    """Prepara quello che la pagina deve mostrare: testi sistemati, totali e avvisi.

    Restituisce un dizionario, per esempio:
        {"indirizzo": "Via Roma 1, Milano", "totale": "€ 700,00 + IVA",
         "voci": [{"prezzo": "€ 700,00", "unita": "mq", "dettaglio": "Totale voce € 700,00 - € 28,00 al mq"}],
         "errori": [], "mancanze": ["Manca: cliente"]}
    """
    errori, mancanze = gp.controlla_preventivo(preventivo)
    errori = problemi + errori                  # Prima i prezzi non capiti, poi gli errori trovati dal controllo

    righe, totale = [], gp.Decimal("0")
    for voce in preventivo["voci"]:
        prezzo = voce.get("importo", voce.get("prezzo_unitario"))  # Il prezzo scritto, qualunque dei due sia; None se non c'è
        riga = {"prezzo": gp.euro(prezzo) if gp.e_un_numero(prezzo) else "", "unita": voce.get("unita", ""), "dettaglio": ""}
        try:
            importo = gp.importo_voce(voce)     # Il totale della voce, oppure None se manca qualcosa
        except Exception:                       # Con dati scritti male il conto può fallire: in quel caso non mostro il dettaglio (l'errore è già nell'elenco)
            importo = None
        if importo is not None:
            totale += importo
            riga["dettaglio"] = "Totale voce " + gp.euro(importo)
            per_unita = frase_per_unita(voce.get("unita"))      # "al mq", "all'ora", "per unità"...
            if "quantita" in voce and "importo" in voce:
                unitario = gp.unitario_dal_totale(voce)
                if unitario is None:
                    riga["dettaglio"] += f" - il prezzo {per_unita} non verrà scritto, perché la divisione non torna precisa"
                else:
                    riga["dettaglio"] += f" - {gp.euro(unitario)} {per_unita}"
        righe.append(riga)

    return {
        "indirizzo": preventivo["indirizzo"],
        "voci": righe,
        "totale": gp.euro(totale) + " + IVA",
        "errori": errori,
        "mancanze": mancanze,
    }


def nome_del_file(preventivo, bozza):
    """Inventa un nome per il file a partire da cliente e lavoro: 'mario_rossi_rifacimento_bagno'."""
    testo = (preventivo["cliente"] + " " + preventivo["titolo"]).lower()
    testo = unicodedata.normalize("NFKD", testo)                        # Separa ogni lettera accentata nella lettera e nel suo accento: "ș" -> "s" + "◌̦"
    testo = "".join(c for c in testo if not unicodedata.combining(c))    # Butta gli accenti e tiene le lettere: "società" -> "societa", "ștefan" -> "stefan"
    nome = re.sub(r"[^a-z0-9]+", "_", testo).strip("_")[:60]            # Tutto ciò che non è lettera o cifra diventa "_"; [:60] lo accorcia se è lunghissimo
    return (nome or "preventivo") + ("_BOZZA" if bozza else "")        # "x or y" usa y quando x è vuoto


# ---------------------------------------------------------------------------
# Gli indirizzi della pagina. Ogni funzione risponde a un indirizzo:
# @app.route("/anteprima") vuol dire "quando il browser chiede /anteprima,
# esegui la funzione qui sotto e mandagli quello che restituisce".
# ---------------------------------------------------------------------------
@app.route("/")
def pagina():
    """La pagina con le caselle."""
    return render_template("pagina.html", oggi=date.today().isoformat())   # Riempie templates/pagina.html; "oggi" serve per la data già compilata (es. '2026-11-14')


@app.route("/anteprima", methods=["POST"])
def anteprima():
    """Riceve il modulo e risponde con testi sistemati, totali e avvisi. Non salva niente."""
    preventivo, problemi = leggi_modulo(request.get_json(silent=True) or {})    # request.get_json legge i dati mandati dalla pagina; silent=True evita un errore se non sono validi
    return jsonify(riassunto(preventivo, problemi))                             # jsonify trasforma il dizionario nel formato che la pagina sa leggere


@app.route("/crea", methods=["POST"])
def crea():
    """Crea il Word. Se ci sono errori non crea niente e li elenca; se manca qualcosa crea una bozza."""
    preventivo, problemi = leggi_modulo(request.get_json(silent=True) or {})
    impresa, impresa_di_esempio = leggi_impresa()
    errori, mancanze = gp.controlla_preventivo(preventivo)
    errori = problemi + errori + gp.controlla_impresa(impresa)
    if errori:
        return jsonify({"errori": errori}), 400     # 400 è il codice che dice al browser "la richiesta non va bene"

    bozza = len(mancanze) > 0
    documento, totale = gp.componi_documento(preventivo, impresa, bozza)

    CARTELLA_USCITA.mkdir(exist_ok=True)
    uscita = gp.percorso_libero(CARTELLA_USCITA, nome_del_file(preventivo, bozza))     # Non sovrascrive mai: rossi.docx, poi rossi-2.docx...
    documento.save(uscita)

    # Salva anche i dati: così il preventivo si può rigenerare o correggere, e col tempo si forma l'archivio.
    CARTELLA_ARCHIVIO.mkdir(parents=True, exist_ok=True)
    dati = json.dumps(preventivo, ensure_ascii=False, indent=2)     # ensure_ascii=False lascia le lettere accentate come sono
    (CARTELLA_ARCHIVIO / (uscita.stem + ".json")).write_text(dati + "\n", encoding="utf-8")    # Stesso nome del Word, ma con .json

    avvisi = ["Nel documento ci sono i dati dell'impresa di esempio, non quelli veri."] if impresa_di_esempio else []
    return jsonify({"file": uscita.name, "bozza": bozza, "mancanze": mancanze, "avvisi": avvisi, "totale": gp.euro(totale) + " + IVA"})


@app.route("/sistema", methods=["POST"])
def sistema():
    """Riceve le descrizioni delle voci e le restituisce con l'italiano corretto.

    La pagina manda solo i testi delle descrizioni: {"descrizioni": ["posa piato docia", "..."]}
    Risponde con {"descrizioni": [{"testo": "Posa piatto doccia", "cambiata": true, "scartata": false}, ...]}
    oppure, se la correzione non si può fare, con {"errore": "una frase che spiega perché"}.
    """
    dati = request.get_json(silent=True)
    descrizioni = dati.get("descrizioni") if isinstance(dati, dict) else None
    if not isinstance(descrizioni, list) or not all(isinstance(testo, str) for testo in descrizioni):
        return jsonify({"errore": "Non ho ricevuto le descrizioni da correggere."}), 400
    try:
        return jsonify({"descrizioni": correzione.sistema_descrizioni(descrizioni)})
    except correzione.ErroreCorrezione as errore:
        return jsonify({"errore": str(errore)}), 503        # 503 vuol dire "servizio non disponibile adesso": il resto della pagina continua a funzionare


@app.route("/scarica/<nome>")
def scarica(nome):
    """Manda al browser un Word già creato. <nome> è il pezzo di indirizzo dopo /scarica/."""
    return send_from_directory(CARTELLA_USCITA, nome, as_attachment=True)   # send_from_directory accetta solo file dentro quella cartella; as_attachment lo fa scaricare


if __name__ == "__main__":
    # Questa parte gira solo quando si lancia "python app.py" sul proprio computer.
    # Online il programma verrà avviato in un altro modo, quindi qui dentro non passa: niente debug là fuori.
    # debug=True ricarica il programma da solo quando modifichi un file: comodo mentre si sviluppa.
    app.config["SESSION_COOKIE_SECURE"] = False     # Sul proprio computer la pagina è in http, non https: senza questo non si resterebbe dentro
    app.run(port=8000, debug=True)
