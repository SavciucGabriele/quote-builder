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

## 2026-11-10 — Nei dati va il testo pulito, e il titolo senza il tipo
Le descrizioni si salvano già corrette, perché il Word viene rigenerato dai
dati e un refuso si ristamperebbe a ogni versione. Il titolo non contiene
"Preventivo" o "Consuntivo": lo aggiunge lo script leggendo il campo "tipo".

## 2026-11-10 — Modello Word e dati dell'impresa fuori dal codice
L'impaginazione sta in un file Word con segnaposto come {{cliente}}; lo script
li riempie e aggiunge le righe della tabella. Per cambiare caratteri, larghezze
o aggiungere un logo si modifica il modello in Word, senza toccare il codice.
I dati dell'impresa stanno in un file a parte non pubblicato; se manca, lo
script usa quelli di esempio.

## 2026-11-10 — Errori e mancanze sono due cose diverse
Un file scritto male (campo sconosciuto, numero come testo, importo e quantità
insieme) ferma lo script: è un errore di chi ha prodotto il file. Un dato che
manca (prezzo, cliente) è normale quando si detta, quindi il documento viene
creato lo stesso come BOZZA, con l'elenco di cosa completare. Quell'elenco
servirà poi per fare le domande a chi ha dettato.

## 2026-11-10 — I conti si fanno in decimali esatti
I numeri normali di Python sono approssimati e sbagliavano di un centesimo in
alcuni prodotti quantità per prezzo. Si usa Decimal, con il mezzo centesimo
arrotondato in su.

## 2026-11-10 — Lo script non sovrascrive e non corregge i testi
Un documento già creato non viene mai sovrascritto (max.docx, max-2.docx...),
così una correzione fatta a mano non va persa. Il titolo viene stampato com'è
scritto nei dati, senza toccare maiuscole e minuscole.

## 2026-11-10 — L'ingresso è una conversazione, non una dettatura unica
Dalle sue chat con ChatGPT: manda messaggi brevi, risponde alle domande e
corregge i dati strada facendo (25 metri diventano 28). Lo strumento terrà un
preventivo in bozza e lo aggiornerà a ogni messaggio: un dato nuovo sostituisce
quello vecchio, e l'elenco delle cose mancanti diventa la lista delle domande.

## 2026-11-10 — Le descrizioni non aggiungono lavorazioni
Il modello può scrivere descrizioni complete, prendendo come esempio quelle già
usate, ma non aggiunge lavorazioni non nominate: in un preventivo ogni cosa
descritta è un impegno con il cliente. Prima del documento finale la bozza
viene sempre mostrata.

## 2026-11-10 — I prezzi li mette il titolare, lo strumento ricorda quelli passati
Il titolare usa ChatGPT solo per farsi un'idea dei prezzi di mercato, poi mette
i suoi. Lo strumento non stima prezzi: suggerisce quelli già usati per lavori
simili, presi dall'archivio; se non ce ne sono, la casella resta "da definire".

## 2026-11-10 — Il valore principale è la scrittura professionale
Il titolare fatica con la lingua: la parte più utile è trasformare quello che
dice in descrizioni da preventivo, nello stile dei suoi documenti, prendendoli
come esempio e senza aggiungere lavorazioni non nominate.

## 2026-11-13 — Lo strumento propone, non inserisce
Rivede la decisione del 10/11 sulle descrizioni. Nel documento entra solo ciò
che il titolare ha detto o confermato. Lo strumento può però proporre: voci
che ricorrono nei suoi preventivi (es. la copertura di protezione), prezzi già
usati per lavori simili, dettagli tipici di una lavorazione. Ogni proposta va
confermata prima di entrare nella bozza.

## 2026-11-13 — Una domanda alla volta, e solo se serve al documento
Nelle chat con ChatGPT il titolare non risponde agli elenchi di domande
("Si grazie" a tre domande), mentre risponde sempre a una domanda singola.
Lo strumento chiede una cosa per volta. Le misure si scrivono come le dice lui
("25 mt"), senza indovinare se sono metri lineari, quadri o cubi.

## 2026-11-13 — I messaggi possono essere comandi sulla bozza
Oltre ad aggiungere o correggere un dato, un messaggio può chiedere una
modifica a tutta la bozza ("aumenta di 20%"). Il modello riconosce il comando,
il conto lo fa il codice.

## 2026-11-14 — Modulo guidato al posto della conversazione
Deciso con il titolare. Per prezzi e consigli continua a usare ChatGPT; il
nostro programma serve a compilare e impaginare. L'interfaccia è una pagina
con i campi in ordine (spettabile, data, luogo, poi per ogni voce descrizione,
a corpo o a metri, prezzo). Ogni campo si può dettare o scrivere a mano.
Sostituisce le decisioni del 10/11 e del 13/11 su conversazione, domande e
comandi sulla bozza.

## 2026-11-14 — Chi tocca cosa
Il nome del cliente resta esattamente come viene scritto. Prezzi e indirizzi
li sistema il codice (da "593€" a "€ 593,00"), senza modello. Al modello
linguistico arriva solo la descrizione dei lavori, e solo quando si chiede di
sistemare il testo: nomi, indirizzi e prezzi non gli vengono mai mandati.

## 2026-11-14 — Tre modi di scrivere una voce
A corpo (solo il totale), a misura con il prezzo per unità (il totale lo
calcola il codice), a misura con il totale già deciso (il costo unitario lo
ricava il codice). Nel terzo caso, se la divisione non torna precisa al
centesimo, il costo unitario non viene stampato: conta il totale deciso dal
titolare, e un prezzo arrotondato non farebbe tornare il conto al cliente.