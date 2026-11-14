"""La pagina per compilare un preventivo dal browser.

Si avvia dalla cartella del progetto con:

    python app.py

e si apre nel browser all'indirizzo http://127.0.0.1:8000

Come sono divisi i compiti:
- templates/pagina.html è quello che si vede: le caselle e i pulsanti.
- questo file riceve quello che è stato scritto nelle caselle, lo sistema con
  pulizia.py, lo controlla e crea il Word con genera_preventivo.py.
Tutte le regole (prezzi, indirizzi, conti, controlli) stanno in Python: la
pagina non fa calcoli, chiede a questo programma e mostra la risposta.
"""

import json
import re
from datetime import date

from flask import Flask, jsonify, render_template, request, send_from_directory

import genera_preventivo as gp      # "as gp" è un soprannome: per usare euro() si scrive gp.euro()
from pulizia import leggi_prezzo, sistema_indirizzo

CARTELLA_USCITA = gp.CARTELLA_USCITA                                # output/: dove finiscono i Word
CARTELLA_ARCHIVIO = gp.CARTELLA / "data" / "raw" / "preventivi"     # Dove si salvano i dati di ogni preventivo creato (resta solo sul Mac)

app = Flask(__name__)       # Crea il programma web. __name__ dice a Flask dove cercare la cartella templates/


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


def leggi_voce(numero, dati):
    """Trasforma una voce scritta nella pagina in una voce del preventivo.

    'dati' è un dizionario con i testi delle caselle, per esempio:
        {"descrizione": "Rasatura", "misura": "misura", "quantita": "25",
         "unita": "mq", "prezzo": "700€", "tipo_prezzo": "totale"}
    Restituisce (voce, problemi). La voce è None se la riga è stata lasciata vuota.
    I problemi sono frasi su quello che non è stato capito, es. un prezzo scritto in modo strano.
    """
    testo = {campo: str(dati.get(campo) or "").strip() for campo in ("descrizione", "quantita", "unita", "prezzo")}     # I testi delle caselle senza spazi intorno; una casella mancante diventa ""
    if not any(testo.values()):         # any(...) è True se almeno una casella contiene qualcosa
        return None, []                 # Riga lasciata tutta vuota: si salta

    voce, problemi = {"descrizione": testo["descrizione"]}, []

    prezzo = None
    if testo["prezzo"]:
        prezzo = leggi_prezzo(testo["prezzo"])
        if prezzo is None:
            problemi.append(f'Voce {numero}: non ho capito il prezzo "{testo["prezzo"]}". Scrivilo come 593 oppure 593,50')

    if dati.get("misura") == "misura":
        # Voce a misura: servono quantità e unità, e il prezzo può essere il totale oppure quello per unità.
        if testo["unita"]:
            voce["unita"] = testo["unita"]
        if testo["quantita"]:
            quantita = leggi_prezzo(testo["quantita"])      # Riuso leggi_prezzo anche per le quantità: capisce "8,5" e "25" allo stesso modo
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
    preventivo = {
        "tipo": dati.get("tipo") or "preventivo",
        "cliente": str(dati.get("cliente") or "").strip(),
        "indirizzo": sistema_indirizzo(str(dati.get("indirizzo") or "")),
        "titolo": str(dati.get("titolo") or "").strip(),
        "data": str(dati.get("data") or "").strip(),
        "voci": [],
    }
    problemi = []
    for dati_voce in dati.get("voci") or []:
        voce, problemi_voce = leggi_voce(len(preventivo["voci"]) + 1, dati_voce)    # Il numero della voce è la sua posizione tra quelle non vuote
        if voce is not None:
            preventivo["voci"].append(voce)
            problemi += problemi_voce
    return preventivo, problemi


def riassunto(preventivo, problemi):
    """Prepara quello che la pagina deve mostrare: testi sistemati, totali e avvisi.

    Restituisce un dizionario, per esempio:
        {"indirizzo": "Via Roma 1, Milano", "totale": "€ 700,00 + IVA",
         "voci": [{"prezzo": "€ 700,00", "dettaglio": "Totale voce € 700,00 - € 28,00 al mq"}],
         "errori": [], "mancanze": ["Manca: cliente"]}
    """
    errori, mancanze = gp.controlla_preventivo(preventivo)
    errori = problemi + errori                  # Prima i prezzi non capiti, poi gli errori trovati dal controllo

    righe, totale = [], gp.Decimal("0")
    for voce in preventivo["voci"]:
        prezzo = voce.get("importo", voce.get("prezzo_unitario"))  # Il prezzo scritto, qualunque dei due sia; None se non c'è
        riga = {"prezzo": gp.euro(prezzo) if gp.e_un_numero(prezzo) else "", "dettaglio": ""}
        try:
            importo = gp.importo_voce(voce)     # Il totale della voce, oppure None se manca qualcosa
        except Exception:                       # Con dati scritti male il conto può fallire: in quel caso non mostro il dettaglio (l'errore è già nell'elenco)
            importo = None
        if importo is not None:
            totale += importo
            riga["dettaglio"] = "Totale voce " + gp.euro(importo)
            unita = voce.get("unita") or "unità"
            if "quantita" in voce and "importo" in voce:
                unitario = gp.unitario_dal_totale(voce)
                if unitario is None:
                    riga["dettaglio"] += f" - il prezzo al {unita} non verrà scritto, perché la divisione non torna precisa"
                else:
                    riga["dettaglio"] += f" - {gp.euro(unitario)} al {unita}"
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
    nome = re.sub(r"[^a-z0-9àèéìòù]+", "_", testo).strip("_")[:60]     # Tutto ciò che non è lettera o cifra diventa "_"; [:60] lo accorcia se è lunghissimo
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
    impresa = gp.leggi_json(gp.IMPRESA_VERA if gp.IMPRESA_VERA.exists() else gp.IMPRESA_ESEMPIO)   # Se esiste il file con i dati veri dell'impresa uso quello, altrimenti l'esempio
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

    return jsonify({"file": uscita.name, "bozza": bozza, "mancanze": mancanze, "totale": gp.euro(totale) + " + IVA"})


@app.route("/scarica/<nome>")
def scarica(nome):
    """Manda al browser un Word già creato. <nome> è il pezzo di indirizzo dopo /scarica/."""
    return send_from_directory(CARTELLA_USCITA, nome, as_attachment=True)   # send_from_directory accetta solo file dentro quella cartella; as_attachment lo fa scaricare


if __name__ == "__main__":
    # debug=True ricarica il programma da solo quando modifichi un file: comodo mentre si sviluppa.
    # Va tolto prima di mettere la pagina online. Così com'è, la pagina si apre solo da questo computer.
    app.run(port=8000, debug=True)
