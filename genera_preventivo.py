"""Genera un preventivo (o consuntivo) in Word a partire da un file di dati JSON.

Uso, dalla cartella del progetto:

    python genera_preventivo.py examples/preventivo_esempio.json

Il documento finisce nella cartella output/, con lo stesso nome del file JSON.
"""

import json
import sys
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ---------------------------------------------------------------------------
# Dove si trovano i file. Path(__file__).parent è la cartella in cui sta
# questo script: partendo da lì i percorsi funzionano da qualunque posto
# venga lanciato il programma.
# ---------------------------------------------------------------------------
CARTELLA = Path(__file__).parent
MODELLO = CARTELLA / "data" / "templates" / "modello_preventivo.docx"
IMPRESA_VERA = CARTELLA / "data" / "raw" / "impresa.json"        # resta solo sul Mac
IMPRESA_ESEMPIO = CARTELLA / "examples" / "impresa_esempio.json"  # dati inventati
CARTELLA_USCITA = CARTELLA / "output"


# ---------------------------------------------------------------------------
# Funzioni piccole: ognuna fa una cosa sola
# ---------------------------------------------------------------------------
def leggi_json(percorso):
    """Apre un file JSON e lo restituisce come dizionario Python."""
    with open(percorso, encoding="utf-8") as file:
        return json.load(file)


def euro(numero):
    """Scrive un importo all'italiana: 1234.5 -> '€ 1.234,50'."""
    testo = f"{numero:,.2f}"  # Python lo scrive all'inglese: '1,234.50'
    # Scambio virgole e punti passando per una lettera di appoggio.
    testo = testo.replace(",", "X").replace(".", ",").replace("X", ".")
    return "€ " + testo


def scrivi_quantita(quantita):
    """6 -> '6', 8.5 -> '8,5'. Niente decimali inutili."""
    if quantita == int(quantita):
        return str(int(quantita))
    return str(quantita).replace(".", ",")


def scrivi_data(testo):
    """'2026-09-08' -> '08/09/2026'. Se la data manca, restituisce una riga vuota."""
    if not testo:
        return ""
    return date.fromisoformat(testo).strftime("%d/%m/%Y")


def importo_voce(voce):
    """Importo di una voce: quello scritto, oppure quantità per prezzo unitario.

    È l'unico punto in cui si fanno i conti delle voci: il totale non viene
    mai letto dal file, viene sempre ricalcolato da qui.
    """
    if "importo" in voce:
        return voce["importo"]
    return round(voce["quantita"] * voce["prezzo_unitario"], 2)


def titolo_completo(preventivo):
    """'preventivo' + 'Sostituzione vasca' -> 'Preventivo sostituzione vasca'."""
    titolo = preventivo["titolo"]
    # Abbasso l'iniziale, ma non se il titolo comincia con una sigla (es. 'CDZ').
    if len(titolo) > 1 and titolo[1].islower():
        titolo = titolo[0].lower() + titolo[1:]
    return preventivo["tipo"].capitalize() + " " + titolo


def celle_voce(numero, voce):
    """Prepara i sei testi di una riga: N, descrizione, U.M., quantità, costo unitario, totale."""
    descrizione = voce["descrizione"]
    if "nota" in voce:
        descrizione += f" ({voce['nota']})"

    if "importo" in voce:
        # Voce a corpo: una sola unità, il costo unitario coincide con il totale.
        unita, quantita, unitario = "A corpo", 1, voce["importo"]
    else:
        unita, quantita, unitario = voce.get("unita", ""), voce["quantita"], voce["prezzo_unitario"]

    return [
        str(numero),
        descrizione,
        unita,
        scrivi_quantita(quantita),
        euro(unitario),
        euro(importo_voce(voce)),
    ]


# ---------------------------------------------------------------------------
# Funzioni che scrivono nel documento Word
# ---------------------------------------------------------------------------
def tutti_i_paragrafi(documento):
    """Elenca i paragrafi dove possono esserci segnaposto: testo, intestazione, piè di pagina."""
    paragrafi = list(documento.paragraphs)
    for sezione in documento.sections:
        paragrafi += sezione.header.paragraphs
        paragrafi += sezione.footer.paragraphs
    return paragrafi


def sostituisci_segnaposto(documento, valori):
    """Nel modello i punti da riempire sono scritti così: {{cliente}}.

    Qui ogni segnaposto viene sostituito con il valore vero. Il testo in Word
    è diviso in pezzi chiamati "run", ognuno con la sua formattazione:
    sostituendo dentro il run, grassetto e carattere restano quelli del modello.
    """
    for paragrafo in tutti_i_paragrafi(documento):
        for run in paragrafo.runs:
            for chiave, valore in valori.items():
                segnaposto = "{{" + chiave + "}}"
                if segnaposto in run.text:
                    run.text = run.text.replace(segnaposto, valore)

        # Se resta un '{{' vuol dire che Word ha spezzato un segnaposto in più run
        # (capita quando lo si modifica a mano): meglio accorgersene subito.
        if "{{" in paragrafo.text:
            print("ATTENZIONE: segnaposto non sostituito nel modello:", paragrafo.text.strip())


def aggiungi_riga(tabella, testi, grassetto=()):
    """Aggiunge una riga in fondo alla tabella.

    'testi' sono i sei testi della riga, 'grassetto' i numeri delle colonne
    da scrivere in grassetto (la prima colonna è la 0).
    """
    riga = tabella.add_row()
    for colonna, testo in enumerate(testi):
        if not testo:
            continue  # cella vuota: non c'è niente da scrivere
        paragrafo = riga.cells[colonna].paragraphs[0]
        run = paragrafo.add_run(testo)
        run.bold = colonna in grassetto
        # La descrizione (colonna 1) resta a sinistra, tutto il resto è centrato.
        if colonna != 1:
            paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return riga


# ---------------------------------------------------------------------------
# Il programma vero e proprio
# ---------------------------------------------------------------------------
def main():
    # sys.argv contiene quello che è stato scritto nel terminale dopo "python":
    # [0] è il nome dello script, [1] il file del preventivo.
    if len(sys.argv) != 2:
        print("Uso: python genera_preventivo.py percorso/del/preventivo.json")
        sys.exit(1)

    percorso = Path(sys.argv[1])
    preventivo = leggi_json(percorso)

    # Se esiste il file con i dati veri dell'impresa uso quello, altrimenti l'esempio.
    impresa = leggi_json(IMPRESA_VERA if IMPRESA_VERA.exists() else IMPRESA_ESEMPIO)

    documento = Document(MODELLO)

    # 1. Intestazione e piè di pagina
    sostituisci_segnaposto(documento, {
        "cliente": preventivo["cliente"],
        "indirizzo": preventivo["indirizzo"],
        "data": scrivi_data(preventivo.get("data")),
        "impresa_nome": impresa["nome"],
        "impresa_indirizzo": impresa["indirizzo"],
        "impresa_telefono": impresa["telefono"],
        "impresa_partita_iva": impresa["partita_iva"],
    })

    # 2. Tabella: titolo, una riga per voce, totale
    tabella = documento.tables[0]
    aggiungi_riga(tabella, ["", titolo_completo(preventivo), "", "", "", ""], grassetto=[1])

    totale = 0
    for numero, voce in enumerate(preventivo["voci"], start=1):
        aggiungi_riga(tabella, celle_voce(numero, voce), grassetto=[5])
        totale += importo_voce(voce)

    riga_totale = aggiungi_riga(tabella, ["", "Totale", euro(totale) + " + IVA", "", "", ""], grassetto=[1, 2])
    # Unisco le ultime quattro celle, così il totale ha spazio e non va a capo.
    riga_totale.cells[2].merge(riga_totale.cells[5])

    # 3. Salvataggio
    CARTELLA_USCITA.mkdir(exist_ok=True)
    uscita = CARTELLA_USCITA / (percorso.stem + ".docx")
    documento.save(uscita)
    print(f"Creato {uscita} - {len(preventivo['voci'])} voci, totale {euro(totale)} + IVA")


if __name__ == "__main__":
    main()