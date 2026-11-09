# Decisioni

## 2026-11-09 — Niente listino prezzi fisso
Le voci cambiano da un lavoro all'altro e il prezzo dipende dal cantiere.
Il prezzo arriva dalla dettatura; se manca, il sistema propone quello di
voci simili già usate, oppure lascia la casella vuota ed evidenziata.

## 2026-11-09 — Un progetto, due percorsi
Preventivi dettati ed Excel degli architetti stanno nello stesso progetto
perché condividono l'archivio delle voci e dei prezzi.

## 2026-11-09 — I calcoli li fa il codice
Il modello linguistico capisce cosa è stato dettato, ma importi, totali e
IVA sono calcolati in Python, perché un modello può sbagliare i conti.

## 2026-11-10 — Il preventivo è un file di dati, il Word è solo l'uscita
Ogni preventivo viene salvato come file di dati (cliente, indirizzo, voci,
importi) e il documento Word viene rigenerato da quello. Così i totali sono
sempre calcolati dal codice, l'impaginazione è sempre uguale e per una
revisione basta modificare i dati. Gli stessi file fanno da archivio delle voci.

## 2026-11-10 — Tanti ingressi, un solo passaggio
Vocale, foto di appunti scritti a mano e testo digitato servono solo a
ottenere un testo. Da lì in poi il percorso è unico: lo stesso passaggio
trasforma il testo in voci e lo riscrive in italiano corretto. Aggiungere un
nuovo ingresso non tocca il resto.

## 2026-11-10 — Si parte dai preventivi propri, non dagli Excel dei tecnici
Dall'analisi di 14 preventivi: modello unico, voci quasi sempre a corpo, ed è
lì che nascono gli errori di somma e di formato. Gli Excel dei tecnici hanno
impaginazioni diverse tra loro e vengono dopo.