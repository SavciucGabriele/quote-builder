"""Genera un preventivo (o consuntivo) in Word a partire da un file di dati JSON.

Uso, dalla cartella del progetto:

    python genera_preventivo.py examples/preventivo_esempio.json

Il documento finisce nella cartella output/, con lo stesso nome del file JSON.

Prima di generare, lo script controlla i dati:
- se trova ERRORI (un campo scritto male, un numero tra virgolette...) si ferma
  e li elenca, senza creare niente;
- se MANCA qualcosa (per esempio un prezzo non ancora deciso) crea lo stesso
  il documento, ma come BOZZA: le caselle da completare sono evidenziate.
"""

import json
import math
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement

# ---------------------------------------------------------------------------
# Dove si trovano i file. Path(__file__).parent è la cartella in cui sta
# questo script: partendo da lì i percorsi funzionano da qualunque posto
# venga lanciato il programma.
# ---------------------------------------------------------------------------
CARTELLA = Path(__file__).parent    # Prende il percorso del file in cui ti trovi (__file__) e ne estrae la cartella contenitore (.parent).
MODELLO = CARTELLA / "data" / "templates" / "modello_preventivo.docx"
IMPRESA_VERA = CARTELLA / "data" / "raw" / "impresa.json"        # resta solo sul Mac
IMPRESA_ESEMPIO = CARTELLA / "examples" / "impresa_esempio.json"  # dati inventati
CARTELLA_USCITA = CARTELLA / "output"

# ---------------------------------------------------------------------------
# Le regole sui dati. Sono scritte qui in alto, tutte insieme, così per
# cambiarle non serve cercarle in mezzo al codice.
# ---------------------------------------------------------------------------
TIPI = ("preventivo", "consuntivo")                                            # i soli valori ammessi per "tipo"
CAMPI_PREVENTIVO = ("tipo", "cliente", "indirizzo", "titolo", "data", "voci")  # i soli campi ammessi nel preventivo
CAMPI_VOCE = ("descrizione", "importo", "quantita", "unita", "prezzo_unitario", "nota", "alternativa")  # i soli campi ammessi in una voce
CAMPI_IMPRESA = ("nome", "indirizzo", "telefono", "partita_iva")               # i campi che devono esserci nel file dell'impresa
DA_DEFINIRE = "da definire"         # il testo che compare, evidenziato, al posto di un dato mancante
CENTESIMI = Decimal("0.01")         # serve per arrotondare a due decimali (vedi importo_voce)


# ---------------------------------------------------------------------------
# Funzioni piccole: ognuna fa una cosa sola
# ---------------------------------------------------------------------------
def leggi_json(percorso):
    """Apre un file JSON e lo restituisce come dizionario Python."""
    with open(percorso, encoding="utf-8") as file:
        return json.load(file)      # Output: Un Dizionario/Lista contenente tutti i dati del file JSON (es. preventivo["cliente"])


def manca(dizionario, campo):
    """Dice se un dato non c'è: campo assente, oppure scritto come null o come testo vuoto."""
    return dizionario.get(campo) in (None, "")  # .get restituisce None se il campo non esiste. Output: True o False (es. manca({"importo": 0}, "importo") -> False, perché 0 è un valore vero)


def e_un_numero(valore):
    """Dice se un valore è un numero vero (320 oppure 8.5) e non un testo come "320"."""
    if isinstance(valore, bool) or not isinstance(valore, (int, float)):   # isinstance controlla il tipo; escludo True/False perché per Python sono anche loro numeri (1 e 0)
        return False
    return math.isfinite(valore)    # Esclude anche NaN e Infinity ("non è un numero" e "infinito"), che il JSON di Python accetta ma con cui non si possono fare conti


def decimale(numero):
    """Trasforma un numero in un decimale esatto: 0.1 -> Decimal('0.1').

    I numeri "normali" di Python (float) sono approssimati: 0.1 + 0.2 fa
    0.30000000000000004. Con i soldi non va bene, quindi i conti si fanno
    con Decimal, che calcola come si fa su carta.
    """
    return Decimal(str(numero))     # Passo dal testo (str) perché Decimal(0.1) si porterebbe dietro l'approssimazione, Decimal("0.1") no


def euro(numero):
    """Scrive un importo all'italiana: 1234.5 -> '€ 1.234,50'."""
    numero = decimale(numero).quantize(CENTESIMI, rounding=ROUND_HALF_UP)   # Arrotonda a due decimali "come a scuola": il mezzo centesimo va sempre in su (2.675 -> 2.68)
    testo = f"{numero:,.2f}"  # Python lo scrive all'inglese: '1,234.50'
    # Sostituisce la virgola con una X, poi il punto con la virgola, poi la X con il punto.
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

    Una voce si può scrivere in tre modi:
      a corpo                 -> "importo"
      a misura, prezzo unità  -> "quantita" + "prezzo_unitario"   (il totale lo calcola il codice)
      a misura, totale deciso -> "quantita" + "importo"           (il costo unitario lo ricava il codice)

    È l'unico punto in cui si fanno i conti delle voci: il totale non viene
    mai letto dal file, viene sempre ricalcolato da qui.
    Se il prezzo non c'è ancora restituisce None, cioè "non lo so".
    """
    if not manca(voce, "importo"):
        return decimale(voce["importo"])   # Controlla se nel dizionario della singola voce esiste la parola "importo" (che nel JSON indica un prezzo a corpo, senza quantità)
    if manca(voce, "quantita") or manca(voce, "prezzo_unitario"):
        return None                         # A misura, ma manca la quantità o il prezzo: il conto non si può fare. Output: None
    prodotto = decimale(voce["quantita"]) * decimale(voce["prezzo_unitario"])   # Se non è a corpo, moltiplica la quantità per il prezzo singolo (es. 0.65 * 52.90 = 34.385 esatto)
    return prodotto.quantize(CENTESIMI, rounding=ROUND_HALF_UP)                 # e arrotonda strettamente a 2 decimali, col mezzo centesimo in su (34.385 -> 34.39)


def unitario_dal_totale(voce):
    """Per una voce a misura di cui si conosce il totale, ricava il costo unitario: 700 € per 25 mq -> 28,00.

    Lo restituisce solo se il conto torna preciso al centesimo. Con 700 € per
    24 mq verrebbe 29,1666...: scrivendo 29,17 il cliente rifarebbe il conto e
    troverebbe 700,08. In quel caso restituisce None e la casella resta vuota:
    quello che conta è il totale deciso dal titolare.
    """
    importo, quantita = decimale(voce["importo"]), decimale(voce["quantita"])
    unitario = (importo / quantita).quantize(CENTESIMI, rounding=ROUND_HALF_UP)    # Divide e arrotonda al centesimo: 700 / 25 = 28.00
    if unitario * quantita == importo:      # Controprova: rifacendo la moltiplicazione deve tornare esattamente il totale
        return unitario
    return None


def titolo_completo(preventivo):
    """'preventivo' + 'sostituzione vasca' -> 'Preventivo sostituzione vasca'.

    Il titolo viene scritto esattamente com'è nel file: lo script non tocca
    maiuscole e minuscole, perché non può sapere se "Milano" è un nome proprio.
    Nel JSON va quindi scritto come deve comparire dopo la parola "Preventivo".
    """
    inizio = preventivo["tipo"].capitalize()    # 'preventivo' -> 'Preventivo'
    if manca(preventivo, "titolo"):
        return inizio                           # Senza titolo resta solo 'Preventivo'
    return inizio + " " + preventivo["titolo"]


def celle_voce(numero, voce):
    """Prepara i sei testi di una riga: N, descrizione, U.M., quantità, costo unitario, totale.

    Dove un dato manca, al suo posto mette il testo DA_DEFINIRE.
    """
    descrizione = voce["descrizione"]
    if voce.get("alternativa"):
        descrizione = "In alternativa: " + descrizione     # Una voce "alternativa" si vede nel documento ma non entra nel totale
    if not manca(voce, "nota"):
        descrizione += f" ({voce['nota']})" # Se nel JSON c'è anche una "nota", la aggiunge in fondo tra parentesi tonde.

    if not manca(voce, "importo") and not manca(voce, "quantita"):
        # Voce a misura di cui è stato deciso il totale: il costo unitario si ricava dividendo (se il conto torna).
        unita = voce.get("unita") or ""
        quantita = scrivi_quantita(voce["quantita"])
        unitario = unitario_dal_totale(voce)                    # Un Decimal, oppure None se la divisione non è precisa
        unitario = "" if unitario is None else euro(unitario)   # Una stringa vuota lascia la casella vuota nel Word
    elif not manca(voce, "importo"):
        # Voce a corpo: una sola unità, il costo unitario coincide con il totale.
        unita, quantita, unitario = "A corpo", "1", euro(voce["importo"])
    elif manca(voce, "quantita") and manca(voce, "prezzo_unitario"):
        # Prezzo del tutto assente: non si sa nemmeno se sarà a corpo o a misura.
        unita, quantita, unitario = voce.get("unita") or "", "", DA_DEFINIRE
    else:
        # Se è a misura, legge i valori dal JSON (se manca l'unità, usa una stringa vuota "").
        unita = voce.get("unita") or ""
        quantita = DA_DEFINIRE if manca(voce, "quantita") else scrivi_quantita(voce["quantita"])
        unitario = DA_DEFINIRE if manca(voce, "prezzo_unitario") else euro(voce["prezzo_unitario"])

    importo = importo_voce(voce)    # Un Decimal, oppure None se il conto non si può fare
    return [
        str(numero),
        descrizione,
        unita,
        quantita,
        unitario,
        DA_DEFINIRE if importo is None else euro(importo),
    ]                               # lista di 6 stringhe ["1", "Tubi", "m", "5", "€ 10,00", "€ 50,00"]


# ---------------------------------------------------------------------------
# Controllo dei dati. Queste funzioni non toccano Word: leggono il preventivo
# e restituiscono due elenchi di frasi.
#   errori   -> il file è scritto male: lo script si ferma.
#   mancanze -> il file è scritto bene ma incompleto: esce una BOZZA.
# ---------------------------------------------------------------------------
def controlla_voce(numero, voce):
    """Controlla una voce. Restituisce (errori, mancanze), due liste di frasi."""
    errori, mancanze = [], []
    nome = f"Voce {numero}"         # Come viene chiamata la voce nei messaggi (es. "Voce 3")

    if not isinstance(voce, dict):
        return [f"{nome}: deve essere scritta tra parentesi graffe {{ }}"], []     # Nelle f-string le graffe vere si scrivono doppie: {{ }} stampa { }

    if manca(voce, "descrizione") or not isinstance(voce["descrizione"], str):
        errori.append(f"{nome}: manca la descrizione")
    else:
        nome += f' ("{voce["descrizione"][:40]}")'  # Aggiunge l'inizio della descrizione per riconoscerla (es. 'Voce 3 ("Fornitura e posa piastrelle")'). [:40] prende i primi 40 caratteri

    for campo in voce:              # Scorre i nomi dei campi presenti nella voce (es. "descrizione", "importo")
        if campo not in CAMPI_VOCE:
            errori.append(f'{nome}: campo sconosciuto "{campo}" (forse è scritto male?)')   # Così un "note" al posto di "nota" non viene più ignorato in silenzio

    for campo in ("importo", "quantita", "prezzo_unitario"):
        if not manca(voce, campo) and not e_un_numero(voce[campo]):
            errori.append(f'{nome}: "{campo}" deve essere un numero, senza virgolette e senza € (es. 320 oppure 320.50)')
    for campo in ("unita", "nota"):
        if not manca(voce, campo) and not isinstance(voce[campo], str):
            errori.append(f'{nome}: "{campo}" deve essere un testo tra virgolette')
    if "alternativa" in voce and not isinstance(voce["alternativa"], bool):
        errori.append(f'{nome}: "alternativa" deve essere true oppure false, senza virgolette')
    if errori:
        return errori, mancanze     # Con dati scritti male i controlli qui sotto non avrebbero senso: mi fermo a questi

    for campo in ("importo", "prezzo_unitario"):
        if not manca(voce, campo) and decimale(voce[campo]).as_tuple().exponent < -2:   # exponent conta le cifre dopo la virgola, in negativo: 10.005 -> -3, cioè tre decimali
            errori.append(f'{nome}: "{campo}" ha più di due decimali')
    if not manca(voce, "quantita") and voce["quantita"] <= 0:
        errori.append(f'{nome}: "quantita" deve essere maggiore di zero')

    ha_importo = not manca(voce, "importo")             # True se è stato scritto il totale della voce
    ha_quantita = not manca(voce, "quantita")
    ha_unitario = not manca(voce, "prezzo_unitario")
    if ha_importo and ha_unitario:
        # Due prezzi nella stessa voce: quale dei due varrebbe? ("importo" insieme a "quantita" invece va bene: è una voce a misura col totale già deciso)
        errori.append(f'{nome}: ha sia "importo" sia "prezzo_unitario". Tieni solo uno dei due: il totale della voce oppure il prezzo per unità')
    elif not ha_importo:
        if ha_quantita and not ha_unitario:
            mancanze.append(f"{nome}: manca il prezzo unitario")
        elif ha_unitario and not ha_quantita:
            mancanze.append(f"{nome}: manca la quantità")
        elif not ha_quantita and not ha_unitario:
            mancanze.append(f"{nome}: manca il prezzo")

    return errori, mancanze         # Output: due liste di frasi, es. ([], ['Voce 3 ("Posa piastrelle"): manca il prezzo'])


def controlla_preventivo(preventivo):
    """Controlla tutto il preventivo. Restituisce (errori, mancanze), due liste di frasi."""
    errori, mancanze = [], []

    if not isinstance(preventivo, dict):
        return ["Il file deve contenere un solo preventivo, scritto tra parentesi graffe { }"], []

    for campo in preventivo:
        if campo not in CAMPI_PREVENTIVO:
            errori.append(f'Campo sconosciuto "{campo}" (forse è scritto male?)')

    if preventivo.get("tipo") not in TIPI:
        errori.append('"tipo" deve essere "preventivo" oppure "consuntivo"')

    for campo in ("cliente", "indirizzo", "titolo"):
        if manca(preventivo, campo):
            mancanze.append(f"Manca: {campo}")              # Non è un errore: capita che dettando non venga detto
        elif not isinstance(preventivo[campo], str):
            errori.append(f'"{campo}" deve essere un testo tra virgolette')

    if not manca(preventivo, "data"):
        try:
            date.fromisoformat(preventivo["data"])          # Prova a leggere la data: se non è nel formato giusto Python lancia un errore...
        except (TypeError, ValueError):
            errori.append('"data" deve essere scritta come anno-mese-giorno, es. "2026-09-08"')  # ...che qui viene trasformato in una frase comprensibile

    voci = preventivo.get("voci")
    if not isinstance(voci, list) or not voci:              # "not voci" è True anche per una lista vuota []
        errori.append("Non c'è nessuna voce: un preventivo deve averne almeno una")
        return errori, mancanze

    for numero, voce in enumerate(voci, start=1):
        errori_voce, mancanze_voce = controlla_voce(numero, voce)
        errori += errori_voce       # += tra liste: aggiunge in fondo tutti gli elementi dell'altra lista
        mancanze += mancanze_voce

    return errori, mancanze


def controlla_impresa(impresa):
    """Controlla il file con i dati dell'impresa. Restituisce una lista di errori (vuota se va tutto bene)."""
    if not isinstance(impresa, dict):
        return ["Il file dei dati dell'impresa deve essere scritto tra parentesi graffe { }"]
    errori = []
    for campo in CAMPI_IMPRESA:
        if manca(impresa, campo):
            errori.append(f'Nel file dei dati dell\'impresa manca "{campo}"')
        elif not isinstance(impresa[campo], str):
            # Capita con il telefono scritto senza virgolette: per il JSON diventa un numero, e Word vuole un testo.
            errori.append(f'Nel file dei dati dell\'impresa "{campo}" deve essere un testo tra virgolette (es. "02 0000000")')
    return errori                   # Output: una lista di frasi, es. [] oppure ['Nel file dei dati dell\'impresa manca "telefono"']


# ---------------------------------------------------------------------------
# Funzioni che scrivono nel documento Word
# ---------------------------------------------------------------------------
def tutti_i_paragrafi(documento):
    """Elenca i paragrafi dove possono esserci segnaposto: testo, intestazione, piè di pagina."""
    paragrafi = list(documento.paragraphs)
    for sezione in documento.sections:
        paragrafi += sezione.header.paragraphs
        paragrafi += sezione.footer.paragraphs
    return paragrafi    # Lista contenente tutti gli oggetti paragrafo di Word presenti nel file.


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
                    # Questa serie di cicli for entra nei paragrafi, entra nei "run"
                    # (Word crea un nuovo "vagone" (un nuovo run) ogni volta che cambia la formattazione del testo),
                    # costruisce la stringa con le graffe (es. {{cliente}}) e se la trova nel testo,
                    # la sostituisce con il valore reale del JSON.

        # Se resta un '{{' vuol dire che Word ha spezzato un segnaposto in più run
        # (capita quando lo si modifica a mano): meglio accorgersene subito.
        if "{{" in paragrafo.text:
            print("ATTENZIONE: segnaposto non sostituito nel modello:", paragrafo.text.strip())


def aggiungi_riga(tabella, testi, grassetto=()):    # testi: La lista di 6 stringhe generata da celle_voce. Se scrivi grassetto=[1, 5], gli passi una lista con i numeri delle colonne da fare in grassetto.
    """Aggiunge una riga in fondo alla tabella.

    'testi' sono i sei testi della riga, 'grassetto' i numeri delle colonne
    da scrivere in grassetto (la prima colonna è la 0).
    """
    riga = tabella.add_row()
    # Vieta a Word di spezzare questa riga tra due pagine: se non ci sta tutta, va intera alla pagina dopo.
    # python-docx non ha un comando pronto per questo, quindi si scrive direttamente l'istruzione che usa Word ("cantSplit").
    riga._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    for colonna, testo in enumerate(testi):     # enumerate fornisce il numero della colonna (0, 1, 2...) e il testo
        if not testo:
            continue  # Se la stringa è vuota (es. unità di misura mancante), salta alla colonna dopo per non scrivere nulla.
        paragrafo = riga.cells[colonna].paragraphs[0]   # Prende la cella corretta, seleziona il suo paragrafo di default,
        run = paragrafo.add_run(testo)                  # ci inserisce il testo creando un nuovo "run"
        run.bold = colonna in grassetto                 #  e accende il grassetto solo se il numero di questa colonna è stato indicato nella lista grassetto
        if testo == DA_DEFINIRE:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW    # Un dato mancante viene passato con l'evidenziatore giallo, così salta all'occhio
        # La descrizione (colonna 1) resta a sinistra, tutto il resto è centrato.
        if colonna != 1:
            paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return riga


def percorso_libero(cartella, nome):
    """Trova un nome di file non ancora usato: max.docx, poi max-2.docx, max-3.docx...

    Così lo script non sovrascrive mai un documento già creato: se nel
    frattempo qualcuno l'ha corretto a mano in Word, la correzione non va persa.
    """
    uscita = cartella / (nome + ".docx")
    numero = 2
    while uscita.exists():                          # Finché quel nome è già preso...
        uscita = cartella / f"{nome}-{numero}.docx" # ...prova con il numero successivo (es. output/max-2.docx)
        numero += 1
    return uscita                                   # Output: un percorso, es. output/max-2.docx


def componi_documento(preventivo, impresa, bozza):
    """Costruisce il documento Word in memoria, senza salvarlo. Restituisce (documento, totale).

    È separata da main() perché serve a due programmi: lo script da terminale
    e la pagina web. Tutti e due le passano un preventivo già controllato.
    """
    documento = Document(MODELLO)
    documento.core_properties.title = titolo_completo(preventivo)   # Il titolo nelle proprietà del file (quello che alcuni programmi mostrano al posto del nome)
    documento.core_properties.author = impresa["nome"]

    # 1. Intestazione e piè di pagina
    sostituisci_segnaposto(documento, {
        "cliente": preventivo.get("cliente") or DA_DEFINIRE,    # "x or y" usa y quando x è vuoto o None
        "indirizzo": preventivo.get("indirizzo") or DA_DEFINIRE,
        "data": scrivi_data(preventivo.get("data")),
        "impresa_nome": impresa["nome"],
        "impresa_indirizzo": impresa["indirizzo"],
        "impresa_telefono": impresa["telefono"],
        "impresa_partita_iva": impresa["partita_iva"],
    })                                                  # Tutti i {{...}} nel documento Word vengono rimpiazzati col testo vero

    # 2. Tabella: titolo, una riga per voce, totale
    tabella = documento.tables[0]   # usa aggiungi_riga per scrivere una riga contenente solo il titolo del preventivo nella colonna 1
    titolo = titolo_completo(preventivo) + (" - BOZZA" if bozza else "")
    aggiungi_riga(tabella, ["", titolo, "", "", "", ""], grassetto=[1])

    totale = Decimal("0")           # Si parte da zero "esatto", così anche la somma si fa in decimali
    for numero, voce in enumerate(preventivo["voci"], start=1): # Scorre la lista "voci" dal JSON. enumerate(..., start=1) crea il numerino progressivo (1, 2, 3...)
        alternativa = voce.get("alternativa", False)            # True solo se nel JSON c'è "alternativa": true
        aggiungi_riga(tabella, celle_voce(numero, voce), grassetto=[] if alternativa else [5]) # Per ogni voce aggiunge la riga in tabella (mettendo in grassetto l'ultima colonna, la 5). Le alternative restano senza grassetto, perché non si sommano
        importo = importo_voce(voce)
        if importo is not None and not alternativa:
            totale += importo       # Si sommano solo le voci che hanno un importo e che non sono alternative

    etichetta = "Totale parziale" if bozza else "Totale"
    importo_totale = euro(totale) + " + IVA" + (" (esclusi i dati da definire)" if bozza else "")
    riga_totale = aggiungi_riga(tabella, ["", etichetta, importo_totale, "", "", ""], grassetto=[1, 2]) # "Totale" nella colonna 1, e il numero finale nella colonna 2
    # Unisco le ultime quattro celle, così il totale ha spazio e non va a capo.
    riga_totale.cells[2].merge(riga_totale.cells[5])            # Prende la cella 2 e la fonde (.merge()) con la cella 5
    return documento, totale        # Output: il documento pronto da salvare e il totale come Decimal


# ---------------------------------------------------------------------------
# Il programma vero e proprio
# ---------------------------------------------------------------------------
def leggi_o_esci(percorso):
    """Come leggi_json, ma se il file non c'è o non è un JSON valido lo dice in chiaro e ferma lo script."""
    try:
        return leggi_json(percorso)
    except FileNotFoundError:
        print(f"Non trovo il file {percorso}")
    except json.JSONDecodeError as errore:      # "as errore" dà un nome all'errore, per poterne leggere i dettagli (riga e motivo)
        print(f"Il file {percorso} non è un JSON valido: riga {errore.lineno}, {errore.msg}")
    sys.exit(1)                                 # Qui si arriva solo se c'è stato uno dei due errori. 1 = "finito male"


def main():
    # sys.argv contiene quello che è stato scritto nel terminale dopo "python":
    # [0] è il nome dello script, [1] il file del preventivo.
    if len(sys.argv) != 2:
        print("Uso: python genera_preventivo.py percorso/del/preventivo.json")
        sys.exit(1)

    percorso = Path(sys.argv[1])
    preventivo = leggi_o_esci(percorso)

    # Se esiste il file con i dati veri dell'impresa uso quello, altrimenti l'esempio.
    impresa = leggi_o_esci(IMPRESA_VERA if IMPRESA_VERA.exists() else IMPRESA_ESEMPIO)

    # 0. Controllo dei dati, prima di toccare Word
    errori, mancanze = controlla_preventivo(preventivo)
    errori += controlla_impresa(impresa)    # Aggiunge in fondo gli eventuali errori del file dell'impresa
    if errori:
        print(f"Il documento NON è stato creato. Errori da correggere in {percorso}:")
        for errore in errori:
            print("  -", errore)
        sys.exit(1)
    bozza = len(mancanze) > 0       # True se manca qualcosa: il documento esce come bozza

    documento, totale = componi_documento(preventivo, impresa, bozza)   # Punti 1 e 2: intestazione, piè di pagina e tabella
    etichetta = "Totale parziale" if bozza else "Totale"

    # 3. Salvataggio
    CARTELLA_USCITA.mkdir(exist_ok=True)    # exist_ok=True evita che il programma vada in crash se la cartella c'è già
    uscita = percorso_libero(CARTELLA_USCITA, percorso.stem + ("_BOZZA" if bozza else ""))   # es. output/max.docx, oppure output/max_BOZZA.docx
    documento.save(uscita)

    print(f"Creato {uscita} - {len(preventivo['voci'])} voci, {etichetta.lower()} {euro(totale)} + IVA")
    if bozza:
        print("È una BOZZA. Da completare:")
        for mancanza in mancanze:
            print("  -", mancanza)


if __name__ == "__main__":
    main()
