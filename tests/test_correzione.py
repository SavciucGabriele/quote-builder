"""Test automatici di correzione.py.

Nessuno di questi test usa internet o una chiave vera: al posto di Gemini c'è
una funzione finta che risponde quello che decide il test.

    python -m pytest tests/test_correzione.py
"""

import io
import json
import urllib.error

import pytest

import correzione
from correzione import (
    ErroreCorrezione,
    accettabile,
    chiedi_a_gemini,
    componi_richiesta,
    estrai_testo,
    leggi_elenco,
    leggi_env,
    numeri,
    sistema_descrizioni,
)


def risposta_di_gemini(elenco):
    """Costruisce una risposta con la stessa forma di quelle vere di Gemini."""
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(elenco, ensure_ascii=False)}]}}]}


def gemini_finto(elenco, ricevuto=None):
    """Restituisce una funzione da usare al posto di chiedi_a_gemini: risponde sempre 'elenco'.

    Se si passa una lista 'ricevuto', ci annota quello che le è stato mandato, per poterlo controllare.
    """
    def chiedi(corpo, chiave, modello):
        if ricevuto is not None:
            ricevuto.append({"corpo": corpo, "chiave": chiave, "modello": modello})
        return risposta_di_gemini(elenco)
    return chiedi


@pytest.fixture
def con_chiave(tmp_path, monkeypatch):
    """Fa finta che nel file .env ci sia una chiave, senza toccare quello vero."""
    file = tmp_path / ".env"
    file.write_text("GEMINI_API_KEY=chiave-di-prova\n", encoding="utf-8")
    monkeypatch.setattr(correzione, "FILE_CHIAVE", file)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)     # delenv toglie la variabile del computer, se c'è: così il test vale su ogni computer
    monkeypatch.delenv("GEMINI_MODELLO", raising=False)


# ---------------------------------------------------------------------------
# Il file .env
# ---------------------------------------------------------------------------
def test_leggi_env(tmp_path):
    file = tmp_path / ".env"
    file.write_text('# commento\n\nGEMINI_API_KEY = "abc=123"\nALTRO=x\n', encoding="utf-8")
    assert leggi_env(file) == {"GEMINI_API_KEY": "abc=123", "ALTRO": "x"}


def test_leggi_env_senza_file(tmp_path):
    assert leggi_env(tmp_path / "non_esiste") == {}


# ---------------------------------------------------------------------------
# Domanda e risposta
# ---------------------------------------------------------------------------
def test_la_richiesta_contiene_solo_istruzioni_e_descrizioni():
    corpo = componi_richiesta(["Posa piato docia"])
    testo = corpo["contents"][0]["parts"][0]["text"]
    assert testo == correzione.ISTRUZIONI + '["Posa piato docia"]'
    assert list(corpo) == ["contents"]                      # Nessun altro campo: niente cliente, indirizzo o prezzi


def test_estrai_testo():
    assert estrai_testo(risposta_di_gemini(["a"])) == '["a"]'


def test_estrai_testo_da_una_risposta_senza_testo():
    with pytest.raises(ErroreCorrezione):                   # pytest.raises controlla che l'errore venga davvero lanciato
        estrai_testo({"promptFeedback": {"blockReason": "SAFETY"}})


def test_leggi_elenco_anche_dentro_un_riquadro():
    assert leggi_elenco('```json\n["Posa piatto doccia"]\n```', 1) == ["Posa piatto doccia"]


def test_leggi_elenco_rifiuta_risposte_strane():
    for testo in ("ciao", '["una", "due"]', '{"a": 1}', "[1]"):     # Non JSON, numero sbagliato, non una lista, non testi
        with pytest.raises(ErroreCorrezione):
            leggi_elenco(testo, 1)


# ---------------------------------------------------------------------------
# I controlli sulla correzione
# ---------------------------------------------------------------------------
def test_numeri():
    assert numeri("Posa 2 porte da 80x210, spessore 2,5 cm") == ["2", "2.5", "210", "80"]     # "2,5" viene scritto "2.5": vedi il test sul punto e la virgola più sotto


def test_correzione_normale_accettata():
    assert accettabile("Posa piato docia", "Posa piatto doccia")
    assert accettabile("Solo posa pavimento compreso colla colla e stucco", "Solo posa pavimento compresi colla e stucco")


def test_correzione_che_cambia_un_numero_scartata():
    assert not accettabile("Posa di 2 porte", "Posa di 3 porte")
    assert not accettabile("Posa di due porte", "Posa di 2 porte")


def test_correzione_che_aggiunge_o_toglie_troppo_scartata():
    assert not accettabile("Imbiancatura bagno", "Imbiancatura del bagno con due mani di idropittura lavabile bianca, compresa la preparazione delle pareti")
    assert not accettabile("Rimozione di rivestimento in piastrelle, discesa, carico e trasporto alla discarica autorizzata", "Rimozione")
    assert not accettabile("Imbiancatura bagno", "   ")


# ---------------------------------------------------------------------------
# sistema_descrizioni
# ---------------------------------------------------------------------------
def test_sistema_descrizioni(con_chiave):
    ricevuto = []
    chiedi = gemini_finto(["Posa piatto doccia", "Imbiancatura bagno"], ricevuto)
    risultati = sistema_descrizioni(["posa piato docia", "", "Imbiancatura bagno"], chiedi)
    assert risultati == [
        {"testo": "Posa piatto doccia", "cambiata": True, "scartata": False},
        {"testo": "", "cambiata": False, "scartata": False},                    # La riga vuota non viene mandata e resta vuota
        {"testo": "Imbiancatura bagno", "cambiata": False, "scartata": False},  # Già giusta
    ]
    assert ricevuto[0]["chiave"] == "chiave-di-prova"
    assert ricevuto[0]["modello"] == correzione.MODELLO_PREDEFINITO
    assert ricevuto[0]["corpo"] == componi_richiesta(["posa piato docia", "Imbiancatura bagno"])


def test_correzione_sospetta_lascia_l_originale(con_chiave):
    risultati = sistema_descrizioni(["Posa di 2 porte"], gemini_finto(["Posa di 3 porte blindate"]))
    assert risultati == [{"testo": "Posa di 2 porte", "cambiata": False, "scartata": True}]


def test_risposta_con_un_numero_diverso_di_voci(con_chiave):
    with pytest.raises(ErroreCorrezione):
        sistema_descrizioni(["una", "due"], gemini_finto(["una sola"]))


def test_senza_chiave(tmp_path, monkeypatch):
    monkeypatch.setattr(correzione, "FILE_CHIAVE", tmp_path / "non_esiste")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ErroreCorrezione, match="manca la chiave"):
        sistema_descrizioni(["Posa piato docia"], gemini_finto(["Posa piatto doccia"]))


def test_niente_da_correggere_non_chiama_gemini(tmp_path, monkeypatch):
    # Con tutte le descrizioni vuote non serve né la chiave né la chiamata
    monkeypatch.setattr(correzione, "FILE_CHIAVE", tmp_path / "non_esiste")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    def chiedi(corpo, chiave, modello):
        raise AssertionError("Gemini non doveva essere chiamato")
    assert sistema_descrizioni(["", "  "], chiedi) == [
        {"testo": "", "cambiata": False, "scartata": False},
        {"testo": "  ", "cambiata": False, "scartata": False},
    ]


def test_troppe_descrizioni(con_chiave):
    with pytest.raises(ErroreCorrezione, match="troppe"):
        sistema_descrizioni(["x"] * (correzione.MASSIMO_DESCRIZIONI + 1), gemini_finto([]))


def test_il_modello_si_puo_cambiare_dal_file_env(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text("GEMINI_API_KEY=k\nGEMINI_MODELLO=un-altro-modello\n", encoding="utf-8")
    monkeypatch.setattr(correzione, "FILE_CHIAVE", file)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODELLO", raising=False)
    assert correzione.impostazioni() == ("k", "un-altro-modello")


# ---------------------------------------------------------------------------
# La chiamata in rete, con una rete finta
# ---------------------------------------------------------------------------
def test_chiamata_riuscita(monkeypatch):
    viste = []
    def urlopen_finto(richiesta, timeout):
        viste.append(richiesta)
        return io.BytesIO(json.dumps(risposta_di_gemini(["ok"])).encode("utf-8"))    # BytesIO imita la risposta che arriva dalla rete
    monkeypatch.setattr(correzione.urllib.request, "urlopen", urlopen_finto)

    assert chiedi_a_gemini({"contents": []}, "la-chiave", "modello-x") == risposta_di_gemini(["ok"])
    richiesta = viste[0]
    assert richiesta.full_url.endswith("/models/modello-x:generateContent")
    assert "la-chiave" not in richiesta.full_url            # La chiave non deve comparire nell'indirizzo
    assert richiesta.get_header("X-goog-api-key") == "la-chiave"


@pytest.mark.parametrize("codice, parola", [(429, "limite"), (403, "chiave"), (404, "modello"), (500, "problema")])
def test_errori_di_gemini_diventano_frasi(monkeypatch, codice, parola):
    # parametrize ripete lo stesso test con ogni coppia (codice, parola)
    def urlopen_finto(richiesta, timeout):
        raise urllib.error.HTTPError(richiesta.full_url, codice, "errore", {}, io.BytesIO(b""))
    monkeypatch.setattr(correzione.urllib.request, "urlopen", urlopen_finto)
    with pytest.raises(ErroreCorrezione, match=parola):
        chiedi_a_gemini({}, "k", "m")


def test_senza_internet(monkeypatch):
    def urlopen_finto(richiesta, timeout):
        raise urllib.error.URLError("rete assente")
    monkeypatch.setattr(correzione.urllib.request, "urlopen", urlopen_finto)
    with pytest.raises(ErroreCorrezione, match="collegarmi"):
        chiedi_a_gemini({}, "k", "m")


def test_certificati_mancanti_non_sembrano_un_problema_di_internet(monkeypatch):
    # Successo davvero sul Mac: internet funzionava, mancavano i certificati di Python
    import ssl
    def urlopen_finto(richiesta, timeout):
        raise urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
    monkeypatch.setattr(correzione.urllib.request, "urlopen", urlopen_finto)
    with pytest.raises(ErroreCorrezione, match="certificato"):
        chiedi_a_gemini({}, "k", "m")


# ---------------------------------------------------------------------------
# Dopo il secondo controllo del codice
# ---------------------------------------------------------------------------
def test_punto_o_virgola_nei_decimali_e_lo_stesso_numero():
    # "2.5 metri" corretto in "2,5 metri" è una correzione giusta: prima veniva scartata
    assert numeri("Tubo da 2.5 metri") == numeri("Tubo da 2,5 metri")
    assert accettabile("Tubo da 2.5 metri", "Tubo da 2,5 metri")


def test_tre_cifre_dopo_il_punto_restano_un_caso_severo():
    # "1.250" può voler dire milleduecentocinquanta, "1,250" uno virgola venticinque: qui non si accetta lo scambio
    assert numeri("1.250 mq") != numeri("1,250 mq")
    assert not accettabile("Scavo di 1.250 mq", "Scavo di 1,250 mq")


def test_le_istruzioni_dicono_di_non_riscrivere_numeri_e_misure():
    assert '"m2"' in correzione.ISTRUZIONI and "in lettere" in correzione.ISTRUZIONI
