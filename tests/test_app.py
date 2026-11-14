"""Test automatici di app.py, la pagina web.

Si lanciano dalla cartella del progetto con:

    python -m pytest tests/test_app.py

Non serve aprire il browser: Flask ha un "finto browser" (test_client) che
manda le richieste alla pagina e legge le risposte.
"""

import pytest

import app as modulo
from app import leggi_modulo, leggi_voce, nome_del_file


def modulo_compilato():
    """Quello che la pagina manda a Python quando le caselle sono compilate bene."""
    return {
        "tipo": "preventivo",
        "cliente": "De Luca Srl",
        "data": "2026-11-14",
        "indirizzo": "via ponte 33 cernusco sul naviglio milano",
        "titolo": "rifacimento bagno",
        "voci": [
            {"descrizione": "Rimozione sanitari", "misura": "corpo", "quantita": "", "unita": "", "prezzo": "650€", "tipo_prezzo": "totale"},
            {"descrizione": "Rasatura pareti", "misura": "misura", "quantita": "25", "unita": "mq", "prezzo": "700", "tipo_prezzo": "totale"},
            {"descrizione": "Posa piastrelle", "misura": "misura", "quantita": "6", "unita": "mq", "prezzo": "55", "tipo_prezzo": "unitario"},
        ],
    }


@pytest.fixture
def browser(tmp_path, monkeypatch):
    """Il finto browser. Durante i test i file finiscono in una cartella temporanea, non in output/ e in data/raw/."""
    monkeypatch.setattr(modulo, "CARTELLA_USCITA", tmp_path / "output")         # monkeypatch cambia una variabile solo per la durata del test
    monkeypatch.setattr(modulo, "CARTELLA_ARCHIVIO", tmp_path / "archivio")
    monkeypatch.setattr(modulo.gp, "IMPRESA_VERA", tmp_path / "non_esiste.json")   # Così i test usano sempre l'impresa di esempio
    return modulo.app.test_client()


# ---------------------------------------------------------------------------
# Dal modulo ai dati
# ---------------------------------------------------------------------------
def test_voce_a_corpo():
    voce, problemi = leggi_voce(1, {"descrizione": " Box doccia ", "misura": "corpo", "prezzo": "593€"})
    assert voce == {"descrizione": "Box doccia", "importo": 593}
    assert problemi == []


def test_voce_a_misura_con_prezzo_totale():
    voce, _ = leggi_voce(1, {"descrizione": "Rasatura", "misura": "misura", "quantita": "25", "unita": "mq", "prezzo": "700", "tipo_prezzo": "totale"})
    assert voce == {"descrizione": "Rasatura", "unita": "mq", "quantita": 25, "importo": 700}


def test_voce_a_misura_con_prezzo_per_unita():
    voce, _ = leggi_voce(1, {"descrizione": "Posa", "misura": "misura", "quantita": "8,5", "unita": "mq", "prezzo": "55", "tipo_prezzo": "unitario"})
    assert voce == {"descrizione": "Posa", "unita": "mq", "quantita": 8.5, "prezzo_unitario": 55}


def test_voce_vuota_viene_saltata():
    assert leggi_voce(1, {"descrizione": "  ", "misura": "corpo", "prezzo": ""}) == (None, [])


def test_prezzo_non_capito_diventa_un_problema():
    voce, problemi = leggi_voce(2, {"descrizione": "Imbiancatura", "misura": "corpo", "prezzo": "circa mille"})
    assert voce == {"descrizione": "Imbiancatura"}
    assert len(problemi) == 1
    assert "Voce 2" in problemi[0]


def test_il_nome_del_cliente_non_viene_toccato():
    dati = modulo_compilato()
    dati["cliente"] = "de luca SRL"
    preventivo, _ = leggi_modulo(dati)
    assert preventivo["cliente"] == "de luca SRL"
    assert preventivo["indirizzo"] == "Via Ponte 33, Cernusco sul Naviglio, MI"


def test_nome_del_file():
    preventivo, _ = leggi_modulo(modulo_compilato())
    assert nome_del_file(preventivo, bozza=False) == "de_luca_srl_rifacimento_bagno"
    assert nome_del_file(preventivo, bozza=True) == "de_luca_srl_rifacimento_bagno_BOZZA"


# ---------------------------------------------------------------------------
# La pagina
# ---------------------------------------------------------------------------
def test_la_pagina_si_apre(browser):
    risposta = browser.get("/")
    assert risposta.status_code == 200              # 200 vuol dire "tutto bene"
    assert "Spettabile" in risposta.get_data(as_text=True)


def test_anteprima_sistema_e_fa_i_conti(browser):
    dati = browser.post("/anteprima", json=modulo_compilato()).get_json()
    assert dati["indirizzo"] == "Via Ponte 33, Cernusco sul Naviglio, MI"
    assert dati["totale"] == "€ 1.680,00 + IVA"     # 650 + 700 + 6 x 55
    assert dati["voci"][0]["prezzo"] == "€ 650,00"
    assert dati["voci"][1]["dettaglio"] == "Totale voce € 700,00 - € 28,00 al mq"
    assert dati["voci"][2]["dettaglio"] == "Totale voce € 330,00"
    assert dati["errori"] == [] and dati["mancanze"] == []


def test_anteprima_con_divisione_che_non_torna(browser):
    dati = modulo_compilato()
    dati["voci"][1]["quantita"] = "24"
    risposta = browser.post("/anteprima", json=dati).get_json()
    assert "non verrà scritto" in risposta["voci"][1]["dettaglio"]


def test_crea_il_word_e_salva_i_dati(browser, tmp_path):
    risposta = browser.post("/crea", json=modulo_compilato())
    dati = risposta.get_json()
    assert risposta.status_code == 200
    assert dati["file"] == "de_luca_srl_rifacimento_bagno.docx"
    assert dati["bozza"] is False
    assert (tmp_path / "output" / "de_luca_srl_rifacimento_bagno.docx").exists()
    assert (tmp_path / "archivio" / "de_luca_srl_rifacimento_bagno.json").exists()
    assert browser.get("/scarica/" + dati["file"]).status_code == 200


def test_crea_due_volte_non_sovrascrive(browser):
    browser.post("/crea", json=modulo_compilato())
    seconda = browser.post("/crea", json=modulo_compilato()).get_json()
    assert seconda["file"] == "de_luca_srl_rifacimento_bagno-2.docx"


def test_senza_un_prezzo_esce_una_bozza(browser):
    dati = modulo_compilato()
    dati["voci"][0]["prezzo"] = ""
    risposta = browser.post("/crea", json=dati).get_json()
    assert risposta["bozza"] is True
    assert risposta["file"].endswith("_BOZZA.docx")
    assert risposta["mancanze"] == ['Voce 1 ("Rimozione sanitari"): manca il prezzo']


def test_con_un_errore_non_crea_niente(browser, tmp_path):
    dati = modulo_compilato()
    dati["voci"][0]["prezzo"] = "boh"
    risposta = browser.post("/crea", json=dati)
    assert risposta.status_code == 400
    assert "non ho capito il prezzo" in risposta.get_json()["errori"][0]
    assert not (tmp_path / "output").exists()


def test_senza_voci_non_crea_niente(browser):
    dati = modulo_compilato()
    dati["voci"] = []
    assert browser.post("/crea", json=dati).status_code == 400
