"""Estrae dall'esportazione di ChatGPT le conversazioni scelte, come file di testo.

ChatGPT esporta tutte le chat dell'account in un unico file, conversations.json.
Questo script lo legge e, per le conversazioni che indichi tu, scrive un file
.txt in data/raw/dettature/ con i messaggi del titolare e, di ogni
risposta di ChatGPT solo la domanda (o, se non ce n'è, l'ultimo paragrafo).

Uso, dalla cartella del progetto:

    python strumenti/estrai_chat.py ~/Downloads/export/conversations.json
        -> elenca tutte le conversazioni, numerate

    python strumenti/estrai_chat.py ~/Downloads/export/conversations.json prezzo
        -> elenca solo quelle con "prezzo" nel titolo

    python strumenti/estrai_chat.py ~/Downloads/export/conversations.json 12 15 31
        -> scrive i file delle conversazioni 12, 15 e 31
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

CARTELLA_PROGETTO = Path(__file__).parent.parent     # strumenti/ -> la cartella del progetto (.parent due volte: si sale di un livello in più)
CARTELLA_USCITA = CARTELLA_PROGETTO / "data" / "raw" / "dettature"  # resta solo sul Mac, come tutto data/raw


# ---------------------------------------------------------------------------
# Lettura del file esportato
# ---------------------------------------------------------------------------
def leggi_conversazioni(percorso):
    """Legge conversations.json e restituisce la lista delle conversazioni, dalla più vecchia alla più recente."""
    with open(percorso, encoding="utf-8") as file:
        dati = json.load(file)
    if isinstance(dati, dict):
        dati = dati.get("conversations", [])       # Per sicurezza: se un giorno il file avesse le chat dentro una chiave "conversations"
    return sorted(dati, key=lambda c: c.get("create_time") or 0)   # Ordina per data di creazione. lambda è una funzione "usa e getta": per ogni chat c restituisce la sua data (0 se manca)


def data_leggibile(conversazione):
    """Trasforma la data della chat (secondi dal 1970, es. 1762805760.5) in '10/11/2026'."""
    secondi = conversazione.get("create_time")
    if not secondi:
        return "??/??/????"
    return datetime.fromtimestamp(secondi).strftime("%d/%m/%Y")


def percorso_conversazione(conversazione):
    """Restituisce i messaggi della chat in ordine, così come si vedono sullo schermo.

    Dentro il file una chat non è una lista ma un "albero": ogni messaggio
    ricorda il messaggio precedente ("parent"). Quando si rigenera una risposta
    o si modifica un messaggio, l'albero si dirama. "current_node" è l'ultimo
    messaggio della versione mostrata: partendo da lì e risalendo di padre in
    padre si ottiene proprio la conversazione visibile, al contrario.
    """
    nodi = conversazione.get("mapping", {})        # Dizionario: id del messaggio -> nodo (con dentro "message" e "parent")
    id_corrente = conversazione.get("current_node")
    messaggi = []
    while id_corrente:                              # Finché c'è un messaggio precedente...
        nodo = nodi.get(id_corrente, {})
        if nodo.get("message"):
            messaggi.append(nodo["message"])
        id_corrente = nodo.get("parent")            # ...sale al precedente. Il primo nodo ha parent None, e il ciclo si ferma
    messaggi.reverse()                              # Erano dall'ultimo al primo: li rimetto in ordine
    return messaggi


def testo_messaggio(messaggio):
    """Estrae il testo di un messaggio. Le foto diventano '[foto]'."""
    contenuto = messaggio.get("content", {})
    pezzi = []
    for parte in contenuto.get("parts") or []:     # "parts" è la lista dei pezzi del messaggio: testi, foto, audio...
        if isinstance(parte, str):
            pezzi.append(parte)
        elif isinstance(parte, dict) and isinstance(parte.get("text"), str):
            pezzi.append(parte["text"])             # Es. la trascrizione di un messaggio vocale
        elif isinstance(parte, dict) and "audio" in str(parte.get("content_type", "")):
            continue                                # Il file audio del vocale: la trascrizione l'ho già presa sopra, quindi lo salto
        elif isinstance(parte, dict) and "image" in str(parte.get("content_type", "")):
            pezzi.append("[foto]")
        elif isinstance(parte, dict):
            pezzi.append("[allegato]")
    return "\n".join(p for p in pezzi if p.strip()).strip()   # Unisce i pezzi andando a capo e scarta quelli vuoti


def domanda_finale(testo):
    """Da una risposta di ChatGPT tiene solo l'ultimo paragrafo con una domanda.

    Se non ci sono domande, tiene l'ultimo paragrafo. Il resto della risposta
    (stime, spiegazioni) non serve: a noi interessa sapere a cosa sta
    rispondendo il titolare nel messaggio dopo.
    """
    paragrafi = [p.strip() for p in re.split(r"\n\s*\n", testo) if p.strip()]   # re.split divide il testo dove c'è una riga vuota
    domande = [p for p in paragrafi if "?" in p]    # Solo i paragrafi che contengono un punto di domanda
    if domande:
        return domande[-1]                          # [-1] è l'ultimo elemento della lista
    return paragrafi[-1] if paragrafi else ""


# ---------------------------------------------------------------------------
# Scrittura dei file
# ---------------------------------------------------------------------------
def testo_conversazione(conversazione):
    """Prepara il contenuto del file .txt di una conversazione."""
    righe = [
        f"TITOLO: {conversazione.get('title') or 'senza titolo'}",
        f"DATA: {data_leggibile(conversazione)}",
        "",
    ]
    for messaggio in percorso_conversazione(conversazione):
        ruolo = messaggio.get("author", {}).get("role")      # "user" = chi scrive, "assistant" = ChatGPT, "system"/"tool" = messaggi interni
        if messaggio.get("metadata", {}).get("is_visually_hidden_from_conversation"):
            continue                                          # Messaggi nascosti che ChatGPT usa internamente: non si vedono sullo schermo, li salto
        tipo = messaggio.get("content", {}).get("content_type")
        if ruolo == "user":
            testo = testo_messaggio(messaggio)
            if testo:
                righe += [f"TITOLARE: {testo}", ""]
        elif ruolo == "assistant" and tipo in ("text", "multimodal_text"):   # Salta i "ragionamenti" e le ricerche web, che non sono la risposta vera
            testo = domanda_finale(testo_messaggio(messaggio))
            if testo:
                righe += [f"CHATGPT: {testo}", ""]
    return "\n".join(righe)


def nome_file(numero, conversazione):
    """'Prezzo fondazione lineare' n. 12 -> '012_prezzo_fondazione_lineare.txt'."""
    titolo = (conversazione.get("title") or "senza titolo").lower()
    titolo = re.sub(r"[^a-z0-9àèéìòù]+", "_", titolo).strip("_")   # Tutto ciò che non è lettera o cifra diventa "_", così il nome è valido su ogni sistema
    return f"{numero:03d}_{titolo[:50]}.txt"         # :03d scrive il numero su tre cifre (12 -> 012), così i file si ordinano bene


# ---------------------------------------------------------------------------
# Il programma vero e proprio
# ---------------------------------------------------------------------------
def elenca(conversazioni, parola=None):
    """Stampa le conversazioni numerate. Con 'parola' mostra solo quelle che la contengono nel titolo."""
    for numero, conversazione in enumerate(conversazioni, start=1):
        titolo = conversazione.get("title") or "senza titolo"
        if parola and parola.lower() not in titolo.lower():
            continue
        print(f"{numero:4d}  {data_leggibile(conversazione)}  {titolo}")


def estrai(conversazioni, numeri):
    """Scrive un file .txt per ogni conversazione indicata."""
    CARTELLA_USCITA.mkdir(parents=True, exist_ok=True)       # parents=True crea anche data/raw se mancasse
    for numero in numeri:
        if not 1 <= numero <= len(conversazioni):
            print(f"  {numero}: non esiste, le conversazioni vanno da 1 a {len(conversazioni)}")
            continue
        conversazione = conversazioni[numero - 1]             # La lista parte da 0, la numerazione da 1
        uscita = CARTELLA_USCITA / nome_file(numero, conversazione)
        if uscita.exists():
            print(f"  {numero}: {uscita.name} esiste già, non lo sovrascrivo")   # Così le correzioni fatte a mano nei .txt non vanno perse
            continue
        uscita.write_text(testo_conversazione(conversazione), encoding="utf-8")
        print(f"  {numero}: creato {uscita.relative_to(CARTELLA_PROGETTO)}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python strumenti/estrai_chat.py percorso/conversations.json [parola | numeri]")
        sys.exit(1)

    percorso = Path(sys.argv[1]).expanduser()       # expanduser trasforma "~" nella tua cartella utente (es. /Users/ciuc)
    try:
        conversazioni = leggi_conversazioni(percorso)
    except FileNotFoundError:
        print(f"Non trovo il file {percorso}")
        sys.exit(1)

    resto = sys.argv[2:]                             # Quello che c'è dopo il percorso del file
    if resto and all(x.isdigit() for x in resto):   # Solo numeri -> si estrae
        estrai(conversazioni, [int(x) for x in resto])
    else:                                            # Niente, oppure una parola -> si elenca
        elenca(conversazioni, " ".join(resto) or None)


if __name__ == "__main__":
    main()
