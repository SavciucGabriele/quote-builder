"""Test automatici di app.py, la pagina web.

Si lanciano dalla cartella del progetto con:

    python -m pytest tests/test_app.py

Non serve aprire il browser: Flask ha un "finto browser" (test_client) che
manda le richieste alla pagina e legge le risposte.
"""

import json

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
    monkeypatch.delenv("IMPRESA_JSON", raising=False)
    monkeypatch.setenv("PASSWORD_PAGINA", "password-di-prova")                  # setenv imposta una variabile del computer solo per la durata del test
    monkeypatch.setitem(modulo.app.config, "SESSION_COOKIE_SECURE", False)      # Il finto browser lavora in http, come sul proprio computer
    modulo.tentativi_sbagliati.clear()
    cliente = modulo.app.test_client()
    cliente.post("/accesso", data={"password": "password-di-prova"})            # Entra, come farebbe una persona
    return cliente


@pytest.fixture
def fuori(browser):
    """Un finto browser che NON è entrato con la password."""
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


# ---------------------------------------------------------------------------
# Correzioni dopo la prima prova della pagina
# ---------------------------------------------------------------------------
from app import frase_per_unita, riassunto


def test_frase_per_unita():
    assert frase_per_unita("mq") == "al mq"
    assert frase_per_unita("ore") == "all'ora"
    assert frase_per_unita("pz") == "al pezzo"
    assert frase_per_unita("giorni") == "al giorno"
    assert frase_per_unita("") == "per unità"                   # Unità non scelta: mai "al unità"
    assert frase_per_unita("fusti") == "per unità (fusti)"      # Unità sconosciuta: nessuna frase sbagliata


def test_dettaglio_con_ore_e_senza_unita():
    voce_ore = {"descrizione": "Manodopera", "unita": "ore", "quantita": 8, "importo": 240}
    voce_senza = {"descrizione": "Posa", "quantita": 4, "importo": 100}
    preventivo = {"indirizzo": "", "voci": [voce_ore, voce_senza]}
    dettagli = [riga["dettaglio"] for riga in riassunto(preventivo, [])["voci"]]
    assert dettagli[0] == "Totale voce € 240,00 - € 30,00 all'ora"
    assert dettagli[1] == "Totale voce € 100,00 - € 25,00 per unità"


def test_unita_dettata_viene_sistemata():
    voce, _ = leggi_voce(1, {"descrizione": "Rasatura", "misura": "misura", "quantita": "25", "unita": "Metri Quadrati", "prezzo": "700", "tipo_prezzo": "totale"})
    assert voce["unita"] == "mq"


def test_quantita_con_tre_decimali_nella_voce():
    voce, problemi = leggi_voce(1, {"descrizione": "Getto", "misura": "misura", "quantita": "2,125", "unita": "mc", "prezzo": "100", "tipo_prezzo": "unitario"})
    assert problemi == [] and voce["quantita"] == 2.125


def test_voce_a_corpo_ignora_quantita_e_unita_nascoste():
    # Si sceglie "A misura", si scrive la quantità, poi si torna a "A corpo": la riga è vuota
    voce, problemi = leggi_voce(1, {"descrizione": "", "misura": "corpo", "quantita": "25", "unita": "mq", "prezzo": "", "tipo_prezzo": "totale"})
    assert voce is None and problemi == []
    # E se la riga ha una descrizione, quantità e unità nascoste non finiscono nella voce
    voce, _ = leggi_voce(1, {"descrizione": "Pulizia", "misura": "corpo", "quantita": "25", "unita": "mq", "prezzo": "300", "tipo_prezzo": "totale"})
    assert voce == {"descrizione": "Pulizia", "importo": 300}


def test_modulo_storto_non_manda_in_crash():
    # Dati che la pagina non manderebbe mai, ma un errore 500 non deve uscire comunque
    for storto in ([1, 2], "ciao", None, {"voci": "ciao"}, {"voci": ["ciao", 5, None]}):
        preventivo, problemi = leggi_modulo(storto)
        assert preventivo["voci"] == []


def test_nome_del_file_toglie_gli_accenti_senza_perdere_lettere():
    preventivo = {"cliente": "Ștefan Țurcanu & Società", "titolo": "Bagno"}
    assert nome_del_file(preventivo, bozza=False) == "stefan_turcanu_societa_bagno"


# ---------------------------------------------------------------------------
# Il pulsante "Sistema il testo"
# ---------------------------------------------------------------------------
def test_sistema_il_testo(browser, monkeypatch):
    # Al posto della vera correzione (che chiamerebbe Gemini) ne metto una finta
    viste = []
    def correzione_finta(descrizioni):
        viste.append(descrizioni)
        return [{"testo": "Posa piatto doccia", "cambiata": True, "scartata": False}]
    monkeypatch.setattr(modulo.correzione, "sistema_descrizioni", correzione_finta)

    risposta = browser.post("/sistema", json={"descrizioni": ["posa piato docia"]})
    assert risposta.status_code == 200
    assert risposta.get_json() == {"descrizioni": [{"testo": "Posa piatto doccia", "cambiata": True, "scartata": False}]}
    assert viste == [["posa piato docia"]]


def test_sistema_il_testo_quando_la_correzione_non_e_disponibile(browser, monkeypatch):
    def correzione_rotta(descrizioni):
        raise modulo.correzione.ErroreCorrezione("manca la chiave")
    monkeypatch.setattr(modulo.correzione, "sistema_descrizioni", correzione_rotta)

    risposta = browser.post("/sistema", json={"descrizioni": ["posa piato docia"]})
    assert risposta.status_code == 503
    assert risposta.get_json() == {"errore": "manca la chiave"}


def test_sistema_il_testo_con_dati_storti(browser):
    for storto in ({"descrizioni": "ciao"}, {"descrizioni": [1, 2]}, [1], {}):
        assert browser.post("/sistema", json=storto).status_code == 400


# ---------------------------------------------------------------------------
# La password d'accesso
# ---------------------------------------------------------------------------
def test_senza_password_non_si_vede_niente(fuori):
    risposta = fuori.get("/")
    assert risposta.status_code == 302 and risposta.headers["Location"] == "/accesso"   # 302 = "vai a quest'altro indirizzo"
    assert "Spettabile" not in risposta.get_data(as_text=True)


def test_senza_password_i_pulsanti_non_funzionano(fuori, monkeypatch):
    def non_deve_succedere(descrizioni):
        raise AssertionError("La correzione non doveva partire")
    monkeypatch.setattr(modulo.correzione, "sistema_descrizioni", non_deve_succedere)
    for indirizzo in ("/anteprima", "/crea", "/sistema"):
        risposta = fuori.post(indirizzo, json=modulo_compilato())
        assert risposta.status_code == 401
    assert fuori.get("/scarica/qualcosa.docx").status_code == 302
    assert not (modulo.CARTELLA_USCITA).exists()            # Nessun file creato


def test_password_sbagliata_e_poi_giusta(fuori):
    risposta = fuori.post("/accesso", data={"password": "sbagliata"})
    assert risposta.status_code == 401 and "Password sbagliata" in risposta.get_data(as_text=True)
    assert fuori.get("/").status_code == 302

    risposta = fuori.post("/accesso", data={"password": "password-di-prova"})
    assert risposta.status_code == 302 and risposta.headers["Location"] == "/"
    assert "Spettabile" in fuori.get("/").get_data(as_text=True)


def test_troppi_tentativi_bloccano_anche_la_password_giusta(fuori):
    for _ in range(modulo.TENTATIVI_MASSIMI):
        fuori.post("/accesso", data={"password": "sbagliata"})
    risposta = fuori.post("/accesso", data={"password": "password-di-prova"})
    assert risposta.status_code == 429 and "Troppi tentativi" in risposta.get_data(as_text=True)
    assert fuori.get("/").status_code == 302


def test_il_blocco_finisce_dopo_dieci_minuti(fuori, monkeypatch):
    for _ in range(modulo.TENTATIVI_MASSIMI):
        fuori.post("/accesso", data={"password": "sbagliata"})
    tra_undici_minuti = modulo.time.time() + 11 * 60
    monkeypatch.setattr(modulo.time, "time", lambda: tra_undici_minuti)     # Sposta l'orologio in avanti invece di aspettare davvero
    assert fuori.post("/accesso", data={"password": "password-di-prova"}).status_code == 302


def test_pagina_chiusa_se_la_password_non_e_impostata(fuori, monkeypatch, tmp_path):
    monkeypatch.setattr(modulo.correzione, "FILE_CHIAVE", tmp_path / "non_esiste")
    for password in ("", "corta"):                          # Mancante, oppure sotto gli 8 caratteri
        monkeypatch.setenv("PASSWORD_PAGINA", password)
        risposta = fuori.get("/accesso")
        assert risposta.status_code == 503 and "non è stata ancora scelta una password" in risposta.get_data(as_text=True)
        assert fuori.post("/accesso", data={"password": password}).status_code == 503
        assert fuori.get("/").status_code == 302


def test_esci(browser):
    assert browser.get("/").status_code == 200
    browser.get("/esci")
    assert browser.get("/").status_code == 302


def test_il_biglietto_viaggia_solo_su_https():
    # Questo test non usa il finto browser, quindi vede il valore vero: online deve restare True
    assert modulo.app.config["SESSION_COOKIE_SECURE"] is True


# ---------------------------------------------------------------------------
# I dati dell'impresa
# ---------------------------------------------------------------------------
def test_avviso_se_nel_word_ci_sono_i_dati_di_esempio(browser):
    risposta = browser.post("/crea", json=modulo_compilato()).get_json()
    assert risposta["avvisi"] == ["Nel documento ci sono i dati dell'impresa di esempio, non quelli veri."]


def test_impresa_presa_dalla_variabile(browser, monkeypatch):
    vera = dict(modulo.gp.leggi_json(modulo.gp.IMPRESA_ESEMPIO))
    monkeypatch.setenv("IMPRESA_JSON", json.dumps(vera))
    assert modulo.leggi_impresa() == (vera, False)
    assert browser.post("/crea", json=modulo_compilato()).get_json()["avvisi"] == []


def test_impresa_scritta_male_nella_variabile(browser, monkeypatch):
    monkeypatch.setenv("IMPRESA_JSON", "{non è json")
    risposta = browser.post("/crea", json=modulo_compilato())
    assert risposta.status_code == 400 and "impresa" in risposta.get_json()["errori"][0]
