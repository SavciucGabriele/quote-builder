"""Test automatici di genera_preventivo.py.

Si lanciano dalla cartella del progetto con:

    python -m pytest

Ogni funzione che comincia con "test_" è una prova: chiama una funzione dello
script e con "assert" dichiara il risultato che ci si aspetta. Se il risultato
è diverso, pytest segnala quale prova è fallita e perché.
"""

from decimal import Decimal

from genera_preventivo import (
    DA_DEFINIRE,
    celle_voce,
    controlla_impresa,
    controlla_preventivo,
    controlla_voce,
    euro,
    importo_voce,
    percorso_libero,
    scrivi_quantita,
    titolo_completo,
)


def preventivo_valido():
    """Un preventivo piccolo e corretto, da cui partono molte prove."""
    return {
        "tipo": "preventivo",
        "cliente": "Mario Rossi",
        "indirizzo": "Via Roma 1, Milano",
        "titolo": "rifacimento bagno",
        "data": "2026-11-10",
        "voci": [
            {"descrizione": "Rimozione sanitari", "importo": 650},
            {"descrizione": "Posa piastrelle", "quantita": 6, "unita": "mq", "prezzo_unitario": 55},
        ],
    }


# ---------------------------------------------------------------------------
# ESERCIZIO: queste tre prove sono da scrivere tu.
# La prima di ogni gruppo è già fatta, come esempio da copiare.
# ---------------------------------------------------------------------------
def test_euro_con_migliaia():
    assert euro(1234.5) == "€ 1.234,50"     # assert: "mi aspetto che sia vero". Se non lo è, la prova fallisce

# 1. Scrivi test_euro_zero: euro(0) deve dare "€ 0,00"
def test_euro_zero():
    assert euro(0) == "€ 0,00"
    
# 2. Scrivi test_euro_negativo: euro(-150) deve dare "€ -150,00" (serve per uno sconto)
def test_euro_negativo():
    assert euro(-150) == "€ -150,00"
    
# 3. Scrivi test_importo_a_corpo: importo_voce di una voce con "importo": 320
#    deve dare Decimal("320")
def test_importo_a_corpo():
    voce = {"descrizione": "Box doccia", "importo": 320}
    assert importo_voce(voce) == Decimal("320")

# ---------------------------------------------------------------------------
# Conti
# ---------------------------------------------------------------------------
def test_importo_a_misura():
    voce = {"descrizione": "Posa piastrelle", "quantita": 6, "prezzo_unitario": 55}
    assert importo_voce(voce) == Decimal("330.00")


def test_arrotondamento_del_mezzo_centesimo():
    # 0,65 x 52,90 = 34,385: il mezzo centesimo deve andare in su.
    # Con i numeri approssimati di Python usciva 34,38.
    voce = {"descrizione": "Rasatura", "quantita": 0.65, "prezzo_unitario": 52.9}
    assert importo_voce(voce) == Decimal("34.39")


def test_importo_mancante():
    assert importo_voce({"descrizione": "Imbiancatura"}) is None
    assert importo_voce({"descrizione": "Velette", "quantita": 4.5}) is None


def test_quantita():
    assert scrivi_quantita(6) == "6"
    assert scrivi_quantita(8.5) == "8,5"


def test_titolo_non_cambia_le_maiuscole():
    assert titolo_completo({"tipo": "preventivo", "titolo": "installazione CDZ"}) == "Preventivo installazione CDZ"
    assert titolo_completo({"tipo": "consuntivo", "titolo": "Milano, via Roma"}) == "Consuntivo Milano, via Roma"


# ---------------------------------------------------------------------------
# Righe della tabella
# ---------------------------------------------------------------------------
def test_celle_voce_a_corpo():
    celle = celle_voce(1, {"descrizione": "Box doccia", "importo": 700, "nota": "stima"})
    assert celle == ["1", "Box doccia (stima)", "A corpo", "1", "€ 700,00", "€ 700,00"]


def test_celle_voce_a_misura():
    celle = celle_voce(3, {"descrizione": "Posa piastrelle", "quantita": 6, "unita": "mq", "prezzo_unitario": 55})
    assert celle == ["3", "Posa piastrelle", "mq", "6", "€ 55,00", "€ 330,00"]


def test_celle_voce_a_misura_con_totale():
    # 700 € per 25 mq: il costo unitario (28,00) si ricava dividendo.
    celle = celle_voce(1, {"descrizione": "Rasatura", "quantita": 25, "unita": "mq", "importo": 700})
    assert celle == ["1", "Rasatura", "mq", "25", "€ 28,00", "€ 700,00"]


def test_celle_voce_a_misura_con_totale_che_non_si_divide():
    # 700 € per 24 mq farebbe 29,1666...: la casella del costo unitario resta vuota, il totale non cambia.
    celle = celle_voce(1, {"descrizione": "Rasatura", "quantita": 24, "unita": "mq", "importo": 700})
    assert celle == ["1", "Rasatura", "mq", "24", "", "€ 700,00"]


def test_celle_voce_senza_prezzo():
    celle = celle_voce(2, {"descrizione": "Imbiancatura"})
    assert celle[4] == DA_DEFINIRE
    assert celle[5] == DA_DEFINIRE


def test_celle_voce_alternativa():
    celle = celle_voce(2, {"descrizione": "Modello B", "importo": 1800, "alternativa": True})
    assert celle[1] == "In alternativa: Modello B"


# ---------------------------------------------------------------------------
# Controllo dei dati
# ---------------------------------------------------------------------------
def test_preventivo_valido_non_ha_problemi():
    assert controlla_preventivo(preventivo_valido()) == ([], [])


def test_prezzo_mancante_e_una_mancanza_non_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"].append({"descrizione": "Imbiancatura"})
    errori, mancanze = controlla_preventivo(preventivo)
    assert errori == []
    assert mancanze == ['Voce 3 ("Imbiancatura"): manca il prezzo']


def test_cliente_mancante_e_una_mancanza():
    preventivo = preventivo_valido()
    del preventivo["cliente"]
    errori, mancanze = controlla_preventivo(preventivo)
    assert errori == []
    assert mancanze == ["Manca: cliente"]


def test_campo_scritto_male_e_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"][0]["note"] = "stima"     # "note" al posto di "nota"
    errori, _ = controlla_preventivo(preventivo)    # "_" è il nome che si dà a un risultato che non serve
    assert len(errori) == 1
    assert 'campo sconosciuto "note"' in errori[0]


def test_due_prezzi_nella_stessa_voce_sono_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"][0]["prezzo_unitario"] = 50      # la voce ha già "importo": 650
    errori, _ = controlla_preventivo(preventivo)
    assert len(errori) == 1
    assert "ha sia" in errori[0]


def test_misura_con_totale_deciso_e_valida():
    preventivo = preventivo_valido()
    preventivo["voci"].append({"descrizione": "Rasatura", "quantita": 25, "unita": "mq", "importo": 700})
    assert controlla_preventivo(preventivo) == ([], [])


def test_numero_scritto_come_testo_e_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"][0]["importo"] = "650"
    errori, _ = controlla_preventivo(preventivo)
    assert len(errori) == 1
    assert "deve essere un numero" in errori[0]


def test_tre_decimali_sono_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"][0]["importo"] = 10.005
    errori, _ = controlla_preventivo(preventivo)
    assert len(errori) == 1
    assert "più di due decimali" in errori[0]


def test_senza_voci_e_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"] = []
    errori, _ = controlla_preventivo(preventivo)
    assert errori == ["Non c'è nessuna voce: un preventivo deve averne almeno una"]


def test_data_scritta_male_e_un_errore():
    preventivo = preventivo_valido()
    preventivo["data"] = "08/09/2026"
    errori, _ = controlla_preventivo(preventivo)
    assert len(errori) == 1
    assert '"data"' in errori[0]


def test_tipo_sconosciuto_e_un_errore():
    preventivo = preventivo_valido()
    preventivo["tipo"] = "fattura"
    errori, _ = controlla_preventivo(preventivo)
    assert len(errori) == 1


def test_importo_non_finito_e_un_errore():
    preventivo = preventivo_valido()
    preventivo["voci"][0]["importo"] = float("nan")     # NaN: il "non numero" che il JSON di Python accetta
    errori, _ = controlla_preventivo(preventivo)
    assert len(errori) == 1
    assert "deve essere un numero" in errori[0]


def test_impresa_valida_non_ha_errori():
    impresa = {"nome": "Impresa Edile Esempio", "indirizzo": "Via Milano 10", "telefono": "02 0000000", "partita_iva": "00000000000"}
    assert controlla_impresa(impresa) == []


def test_impresa_telefono_senza_virgolette_e_un_errore():
    impresa = {"nome": "Impresa Edile Esempio", "indirizzo": "Via Milano 10", "telefono": 20000000, "partita_iva": "00000000000"}
    errori = controlla_impresa(impresa)
    assert len(errori) == 1
    assert '"telefono"' in errori[0]


def test_impresa_campo_mancante_e_un_errore():
    errori = controlla_impresa({"nome": "Impresa Edile Esempio", "indirizzo": "Via Milano 10"})
    assert len(errori) == 2     # mancano telefono e partita IVA


# ---------------------------------------------------------------------------
# Salvataggio
# ---------------------------------------------------------------------------
def test_percorso_libero_non_sovrascrive(tmp_path):
    # tmp_path è una cartella vuota e temporanea che pytest crea apposta per questa prova.
    assert percorso_libero(tmp_path, "max").name == "max.docx"
    (tmp_path / "max.docx").write_text("finto documento")
    assert percorso_libero(tmp_path, "max").name == "max-2.docx"
    (tmp_path / "max-2.docx").write_text("finto documento")
    assert percorso_libero(tmp_path, "max").name == "max-3.docx"


# ---------------------------------------------------------------------------
# Unità e data mancanti (aggiunte dopo la prima prova della pagina)
# ---------------------------------------------------------------------------
def test_voce_a_misura_senza_unita_e_una_mancanza():
    errori, mancanze = controlla_voce(1, {"descrizione": "Posa", "quantita": 6, "prezzo_unitario": 55})
    assert errori == []
    assert mancanze == ['Voce 1 ("Posa"): manca l\'unità di misura']


def test_voce_a_corpo_non_ha_bisogno_dell_unita():
    assert controlla_voce(1, {"descrizione": "Pulizia", "importo": 300}) == ([], [])


def test_celle_voce_senza_unita_scrive_da_definire():
    celle = celle_voce(1, {"descrizione": "Posa", "quantita": 6, "prezzo_unitario": 55})
    assert celle[2] == DA_DEFINIRE


def test_data_mancante_e_una_mancanza():
    preventivo = {"tipo": "preventivo", "cliente": "X", "indirizzo": "Via Roma 1", "titolo": "T",
                  "voci": [{"descrizione": "Pulizia", "importo": 300}]}
    errori, mancanze = controlla_preventivo(preventivo)
    assert errori == [] and mancanze == ["Manca: data"]
