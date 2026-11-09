# cantiere-preventivi-ai

Strumento per aiutare una piccola impresa edile a preparare preventivi e
consuntivi dettandoli a voce, invece di scriverli e impaginarli a mano in
Word ed Excel.

**Stato: fase iniziale, non c'è ancora codice funzionante.**

## Il problema

Il titolare sa cosa scrivere nel preventivo, ma scriverlo al computer e
impaginarlo gli costa molto tempo, e i documenti restano arretrati.
Dettare a un assistente generico aiuta solo in parte: non ricorda i prezzi
già usati, impagina ogni volta in modo diverso e il testo va comunque
copiato a mano nel documento.

## L'idea

Un solo progetto con due percorsi che condividono un archivio delle voci
e dei prezzi già usati.

- **Da vocale a documento:** il titolare detta le lavorazioni, il sistema
  produce il preventivo già impaginato.
- **Excel di architetti e geometri:** il sistema legge le voci già scritte
  e aiuta a compilare i prezzi senza toccare il resto del file.

Il prezzo lo decide sempre il titolare. Il sistema può proporre quello
usato per lavorazioni simili in passato, ma non lo inventa. I calcoli
(importi, totali, IVA) li fa il codice, non il modello linguistico.

## A che punto è

- [ ] Generare un preventivo impaginato da una lista di voci
- [ ] Ricavare la lista di voci da un testo
- [ ] Trascrivere un vocale
- [ ] Archivio delle voci e suggerimento dei prezzi
- [ ] Compilazione degli Excel ricevuti
- [ ] Uso dal telefono

## Dati

Il repository non contiene documenti, clienti o prezzi reali: gli esempi
sono inventati.
