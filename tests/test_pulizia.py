"""Test automatici di pulizia.py: prezzi e indirizzi.

Si lanciano dalla cartella del progetto con:

    python -m pytest tests/test_pulizia.py
"""

from decimal import Decimal

from pulizia import leggi_prezzo, sistema_indirizzo, sistema_prezzo


# ---------------------------------------------------------------------------
# ESERCIZIO: queste tre prove sono da scrivere tu.
# ---------------------------------------------------------------------------
# 1. Scrivi test_prezzo_con_simbolo: leggi_prezzo("593€") deve dare Decimal("593.00")
def test_prezzo_con_simbolo():
    assert leggi_prezzo("593€") == Decimal("593.00")

# 2. Scrivi test_sistema_prezzo: sistema_prezzo("593€") deve dare "€ 593,00"
def test_sistema_prezzo():
    assert sistema_prezzo("593€") == "€ 593,00"

# 3. Scrivi test_indirizzo_di_citta: sistema_indirizzo("via roma 1 milano")
#    deve dare "Via Roma 1, Milano"
def test_indirizzo_di_citta():
    assert sistema_indirizzo("via roma 1 milano") == "Via Roma 1, Milano"
# ---------------------------------------------------------------------------
# Prezzi
# ---------------------------------------------------------------------------
def test_prezzo_scritto_in_tanti_modi():
    # Tutti questi modi di scrivere devono dare lo stesso numero.
    for testo in ("593", "€ 593", "593 €", "593 euro", "593,00", "593.00", " 593,0 "):
        assert leggi_prezzo(testo) == Decimal("593.00")


def test_prezzo_con_i_centesimi():
    assert leggi_prezzo("593,5") == Decimal("593.50")
    assert leggi_prezzo("1200,5") == Decimal("1200.50")


def test_prezzo_con_le_migliaia():
    assert leggi_prezzo("1.200") == Decimal("1200.00")          # il punto seguito da tre cifre separa le migliaia
    assert leggi_prezzo("1.200,50") == Decimal("1200.50")
    assert leggi_prezzo("1 200") == Decimal("1200.00")
    assert leggi_prezzo("1.250.000") == Decimal("1250000.00")


def test_prezzo_negativo_per_gli_sconti():
    assert leggi_prezzo("-150") == Decimal("-150.00")


def test_prezzo_non_chiaro():
    # Quando non è sicuro, leggi_prezzo non indovina: restituisce None.
    for testo in ("", "circa mille", "1,234", "12.34.56", "593 + iva", "€", "٥٩٣", None):
        assert leggi_prezzo(testo) is None


def test_sistema_prezzo_con_migliaia_e_centesimi():
    assert sistema_prezzo("1200,5") == "€ 1.200,50"
    assert sistema_prezzo("boh") is None


# ---------------------------------------------------------------------------
# Indirizzi
# ---------------------------------------------------------------------------
def test_indirizzo_scritto_di_getto():
    assert sistema_indirizzo("via ponte 33 Cernusco sul Naviglio milano") == "Via Ponte 33, Cernusco sul Naviglio, MI"


def test_indirizzo_gia_a_posto_non_cambia():
    assert sistema_indirizzo("Via Ponte 33, Cernusco sul Naviglio, MI") == "Via Ponte 33, Cernusco sul Naviglio, MI"


def test_indirizzo_tutto_maiuscolo():
    assert sistema_indirizzo("VIA XX SETTEMBRE 5 BRUGHERIO MONZA") == "Via XX Settembre 5, Brugherio, MB"


def test_indirizzo_con_data_nel_nome_della_via():
    assert sistema_indirizzo("via 25 aprile 12 carugate mi") == "Via 25 Aprile 12, Carugate, MI"


def test_indirizzo_con_cap_e_sigla_tra_parentesi():
    assert sistema_indirizzo("via roma 3 20063 cernusco sul naviglio (mi)") == "Via Roma 3, 20063 Cernusco sul Naviglio, MI"


def test_indirizzo_con_piu_civici():
    assert sistema_indirizzo("via ada negri 6/8/10 bussero") == "Via Ada Negri 6/8/10, Bussero"


def test_indirizzo_con_apostrofi():
    assert sistema_indirizzo("via dell'olmo 7 cassano d'adda milano") == "Via dell'Olmo 7, Cassano d'Adda, MI"
    assert sistema_indirizzo("via la pira 12 sant'angelo lodigiano lodi") == "Via La Pira 12, Sant'Angelo Lodigiano, LO"


def test_indirizzo_con_la_parola_numero():
    assert sistema_indirizzo("via roma n. 3 milano") == "Via Roma 3, Milano"
    assert sistema_indirizzo("Via Ponte n°33 Cernusco") == "Via Ponte 33, Cernusco"


def test_indirizzo_con_bis():
    assert sistema_indirizzo("via garibaldi 12 bis lodi") == "Via Garibaldi 12 bis, Lodi"
    assert sistema_indirizzo("via garibaldi 12bis codogno lodi") == "Via Garibaldi 12bis, Codogno, LO"


def test_indirizzo_con_la_virgola_prima_del_civico():
    assert sistema_indirizzo("via ponte, 33, cernusco, mi") == "Via Ponte 33, Cernusco, MI"


def test_indirizzo_con_la_parola_provincia():
    assert sistema_indirizzo("via ponte 33 cernusco sul naviglio provincia di milano") == "Via Ponte 33, Cernusco sul Naviglio, MI"


def test_provincia_che_fa_parte_del_nome():
    # "Venezia" qui non è la provincia: fa parte del nome del posto.
    assert sistema_indirizzo("via lepanto 4 lido di venezia") == "Via Lepanto 4, Lido di Venezia"


def test_indirizzo_senza_civico_ma_con_la_virgola():
    assert sistema_indirizzo("piazza salgari, cernusco sul naviglio") == "Piazza Salgari, Cernusco sul Naviglio"


def test_indirizzo_senza_civico_e_senza_virgole():
    # Qui non si può sapere dove finisce la via: si sistemano solo le maiuscole.
    assert sistema_indirizzo("piazza salgari cernusco sul naviglio") == "Piazza Salgari Cernusco sul Naviglio"


def test_indirizzo_vuoto():
    assert sistema_indirizzo("") == ""
    assert sistema_indirizzo("   ") == ""