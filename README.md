# preventivi-ai

Strumento per aiutare una piccola impresa edile a preparare preventivi e
consuntivi senza scriverli e impaginarli a mano in Word.

**Stato: in sviluppo. La pagina funziona sul computer di chi sviluppa; mancano
la correzione dei testi e la messa online.**

## Il problema

Il titolare sa cosa mettere nel preventivo, ma scriverlo al computer e
impaginarlo gli costa molto tempo, e i documenti restano arretrati. Nei
documenti fatti a mano finiscono anche errori di somma e di formato.

## Come funziona

Una pagina web con le caselle in ordine: cliente, data, luogo, lavoro e poi le
voci. Ogni casella si può scrivere o dettare con il microfono della tastiera.
Il programma sistema prezzi e indirizzi, fa i conti e crea il documento Word
con l'impaginazione dell'impresa.

Una voce può essere a corpo, a misura con il prezzo per unità, oppure a misura
con il totale già deciso. Se manca un dato il documento esce come BOZZA, con
le caselle da completare evidenziate.

## A che punto è

- [x] Dal file di dati al Word, con controlli, bozze e conti esatti
- [x] Pulizia di prezzi e indirizzi
- [x] Pagina per compilare il preventivo
- [x] Correzione dell'italiano nelle descrizioni
- [ ] Pagina online, per telefono e computer

## Come si usa

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Poi si apre `http://127.0.0.1:8000` nel browser. Per lanciare i test:
`python -m pytest`.

## Dati

Il repository non contiene documenti, clienti o prezzi reali: gli esempi sono
inventati.