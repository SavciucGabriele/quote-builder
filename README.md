# preventivi-ai

Una pagina web che aiuta una piccola impresa edile a preparare preventivi e
consuntivi: si compilano (o si dettano) poche caselle e il programma fa i
conti, sistema prezzi e indirizzi, corregge l'italiano e crea il documento
Word con l'impaginazione dell'impresa.

*In English: a small Flask web app that lets a construction contractor fill in
(or dictate) a quote from his phone and get a correctly formatted Word
document. Exact decimal arithmetic, rule-based cleaning of prices and
addresses, and an optional LLM step that only fixes spelling and grammar,
with code-level guardrails. Code and comments are in Italian, because the
user and the domain are.*

<img src="docs/pagina.png" alt="La pagina vista dal telefono" width="300">

## Il problema

L'ho fatto per aiutare mio padre, che ha una piccola impresa edile. 
Lui sa che cosa mettere nel preventivo, ma scriverlo al computer e
impaginarlo gli costa molto tempo, e i documenti restano arretrati. Nei
documenti fatti a mano finiscono anche errori di somma e di formato.

Lo strumento è in uso: il primo preventivo vero, sedici voci, è stato
compilato in circa cinque minuti.

## Come funziona

1. **Si compila la pagina.** Cliente, data, luogo, lavoro e poi le voci. Ogni
   casella si può scrivere o dettare con il microfono della tastiera.
2. **Il codice sistema e controlla.** `593€` diventa `€ 593,00`,
   `via ponte 33 robecco sul naviglio milano` diventa
   `Via Ponte 33, Robecco sul Naviglio, MI`. Il totale si aggiorna mentre si
   scrive.
3. **Se serve, si corregge l'italiano.** Un pulsante manda le sole descrizioni
   dei lavori a un modello linguistico (Gemini), che corregge ortografia e
   grammatica. Sotto ogni testo cambiato resta quello di prima, e si può
   tornare indietro.
4. **Si scarica il Word.** Se manca un dato il documento esce come BOZZA, con
   le caselle da completare evidenziate in giallo.

Una voce può essere a corpo, a misura con il prezzo per unità, oppure a misura
con il totale già deciso.

## Scelte di progetto

Le decisioni, con il motivo di ognuna, sono in [DECISIONS.md](DECISIONS.md),
comprese quelle poi abbandonate. Le principali:

- **I conti li fa il codice, mai il modello.** Importi e totali sono calcolati
  in Python con decimali esatti (`Decimal`), perché con i numeri normali
  alcuni prodotti sbagliavano di un centesimo.
- **Il modello linguistico propone, il codice controlla.** Una correzione che
  cambia un numero, o che allunga o accorcia troppo il testo, viene scartata:
  in un preventivo ogni cosa scritta è un impegno con il cliente.
- **Al modello arrivano solo le descrizioni dei lavori.** Nomi, indirizzi e
  prezzi non lasciano il programma.
- **Errori e mancanze sono cose diverse.** Un dato scritto male blocca il
  documento, un dato che manca produce una bozza.
- **Chiuso finché non è configurato.** Senza una password impostata la pagina
  non si apre.

## Com'è fatto

| File | Cosa fa |
|---|---|
| `genera_preventivo.py` | Controlla i dati, fa i conti e scrive il Word a partire dal modello |
| `pulizia.py` | Sistema prezzi, quantità, indirizzi e unità di misura |
| `correzione.py` | Chiede a Gemini di correggere le descrizioni e controlla la risposta |
| `app.py` | La pagina web (Flask): accesso con password, anteprima, creazione del Word |
| `templates/` | L'HTML della pagina e della schermata d'accesso |
| `tests/` | I test automatici |
| `examples/` | Un preventivo, una bozza e un'impresa inventati |

## Come si prova

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Nel file `.env` va scelta una password per la pagina (`PASSWORD_PAGINA`, almeno
8 caratteri). La chiave di Gemini è facoltativa: senza, funziona tutto tranne
la correzione dei testi. Poi:

```bash
python app.py
```

e si apre `http://127.0.0.1:8000` nel browser. Si può anche creare un Word
senza la pagina, da un file di dati:

```bash
python genera_preventivo.py examples/preventivo_esempio.json
```

I test si lanciano con `python -m pytest`. Nessuno usa internet o una chiave
vera: al posto di Gemini c'è una risposta finta.

Online il programma gira con Gunicorn (`gunicorn app:app`) e legge password,
chiave e dati dell'impresa dalle variabili d'ambiente invece che dal file
`.env`.

## Limiti noti

- Ricaricando la pagina si perde quello che è stato scritto.
- Un preventivo già creato non si può riaprire per modificarlo.
- Dalla pagina non si possono ancora inserire voci "in alternativa" e note,
  che il generatore del Word invece gestisce.
- La pulizia degli indirizzi segue delle regole: funziona con gli indirizzi
  italiani più comuni, non con tutti.
- La password è una sola, uguale per chi usa la pagina.
- Online, con il piano gratuito di Render, la pagina si spegne dopo 15 minuti senza uso e la prima apertura richiede circa un minuto.

## Dati

Il repository non contiene documenti, clienti o prezzi reali: gli esempi sono
inventati. I dati veri dell'impresa e i preventivi stanno fuori da Git.

## Come è stato sviluppato

È il mio primo progetto di questo tipo. Il codice l'ha scritto un assistente
AI (Claude), su mie indicazioni. La parte mia è stata capire il problema
insieme a mio padre, che usa lo strumento; decidere che cosa doveva fare e
che cosa no (le scelte e i motivi sono in [DECISIONS.md](DECISIONS.md));
provare ogni versione con lui e riportare i problemi; metterlo online. I file
Python sono commentati riga per riga perché l'obiettivo era anche capire
tutto il codice.
