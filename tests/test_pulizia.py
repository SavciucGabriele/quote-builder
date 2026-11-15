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
    assert sistema_indirizzo("via ponte 33 Robecco sul Naviglio milano") == "Via Ponte 33, Robecco sul Naviglio, MI"


def test_indirizzo_gia_a_posto_non_cambia():
    assert sistema_indirizzo("Via Ponte 33, Robecco sul Naviglio, MI") == "Via Ponte 33, Robecco sul Naviglio, MI"


def test_indirizzo_tutto_maiuscolo():
    assert sistema_indirizzo("VIA XX SETTEMBRE 5 BRUGHERIO MONZA") == "Via XX Settembre 5, Brugherio, MB"


def test_indirizzo_con_data_nel_nome_della_via():
    assert sistema_indirizzo("via 25 aprile 12 carugate mi") == "Via 25 Aprile 12, Carugate, MI"


def test_indirizzo_con_cap_e_sigla_tra_parentesi():
    assert sistema_indirizzo("via roma 3 20087 robecco sul naviglio (mi)") == "Via Roma 3, 20087 Robecco sul Naviglio, MI"


def test_indirizzo_con_piu_civici():
    assert sistema_indirizzo("via ada negri 6/8/10 bussero") == "Via Ada Negri 6/8/10, Bussero"


def test_indirizzo_con_apostrofi():
    assert sistema_indirizzo("via dell'olmo 7 cassano d'adda milano") == "Via dell'Olmo 7, Cassano d'Adda, MI"
    assert sistema_indirizzo("via la pira 12 sant'angelo lodigiano lodi") == "Via La Pira 12, Sant'Angelo Lodigiano, LO"


def test_indirizzo_con_la_parola_numero():
    assert sistema_indirizzo("via roma n. 3 milano") == "Via Roma 3, Milano"
    assert sistema_indirizzo("Via Ponte n°33 Robecco") == "Via Ponte 33, Robecco"


def test_indirizzo_con_bis():
    assert sistema_indirizzo("via garibaldi 12 bis lodi") == "Via Garibaldi 12 bis, Lodi"
    assert sistema_indirizzo("via garibaldi 12bis codogno lodi") == "Via Garibaldi 12bis, Codogno, LO"


def test_indirizzo_con_la_virgola_prima_del_civico():
    assert sistema_indirizzo("via ponte, 33, robecco, mi") == "Via Ponte 33, Robecco, MI"


def test_indirizzo_con_la_parola_provincia():
    assert sistema_indirizzo("via ponte 33 robecco sul naviglio provincia di milano") == "Via Ponte 33, Robecco sul Naviglio, MI"


def test_provincia_che_fa_parte_del_nome():
    # "Venezia" qui non è la provincia: fa parte del nome del posto.
    assert sistema_indirizzo("via lepanto 4 lido di venezia") == "Via Lepanto 4, Lido di Venezia"


def test_indirizzo_senza_civico_ma_con_la_virgola():
    assert sistema_indirizzo("piazza italia, robecco sul naviglio") == "Piazza Italia, Robecco sul Naviglio"


def test_indirizzo_senza_civico_e_senza_virgole():
    # Qui non si può sapere dove finisce la via: si sistemano solo le maiuscole.
    assert sistema_indirizzo("piazza italia robecco sul naviglio") == "Piazza Italia Robecco sul Naviglio"


def test_indirizzo_vuoto():
    assert sistema_indirizzo("") == ""
    assert sistema_indirizzo("   ") == ""

# ---------------------------------------------------------------------------
# Quantità e unità di misura (aggiunte dopo la prima prova della pagina)
# ---------------------------------------------------------------------------
from pulizia import leggi_quantita, sistema_unita


def test_quantita_con_tre_decimali():
    # Per i volumi (mc) capitano tre decimali: 2,125 non va rifiutata come un prezzo
    assert leggi_quantita("2,125") == Decimal("2.125")
    assert leggi_quantita("25") == Decimal("25")
    assert leggi_quantita("8,5") == Decimal("8.5")


def test_quantita_troppo_precisa_o_strana():
    assert leggi_quantita("2,1256") is None
    assert leggi_quantita("circa dieci") is None


def test_prezzo_resta_a_due_decimali():
    # Il prezzo non deve cambiare: tre decimali restano ambigui
    assert leggi_prezzo("2,125") is None


def test_unita_dettate_diventano_sigle():
    assert sistema_unita("metri quadrati") == "mq"
    assert sistema_unita("Metri Quadri") == "mq"
    assert sistema_unita("m2") == "mq"
    assert sistema_unita("m²") == "mq"
    assert sistema_unita("metri cubi") == "mc"
    assert sistema_unita("metri lineari") == "ml"
    assert sistema_unita("metri") == "mt"
    assert sistema_unita("pezzi") == "pz"
    assert sistema_unita("ora") == "ore"
    assert sistema_unita("H") == "ore"


def test_unita_con_maiuscole_punti_e_spazi():
    assert sistema_unita("  MQ. ") == "mq"
    assert sistema_unita("Mt.") == "mt"
    assert sistema_unita("m  quadrati") == "mq"


def test_unita_sconosciuta_resta_com_e_ma_in_minuscolo():
    assert sistema_unita("Kg") == "kg"
    assert sistema_unita("Giorni") == "giorni"
    assert sistema_unita("") == ""


# ---------------------------------------------------------------------------
# Trovati con il controllo a tappeto prima di pubblicare
# ---------------------------------------------------------------------------
from pulizia import pulisci_testo


def test_indirizzo_fatto_solo_di_virgole():
    assert sistema_indirizzo(",,,") == ""
    assert sistema_indirizzo(" , ") == ""


def test_pulisci_testo_toglie_i_caratteri_invisibili():
    assert pulisci_testo("Mario\x00 Rossi\x0b") == "Mario Rossi"
    assert pulisci_testo("Posa \ud83d") == "Posa "                  # Mezza emoji (capita se un testo viene tagliato a metà)
    assert pulisci_testo("riga 1\nriga 2\tfine") == "riga 1\nriga 2\tfine"    # A capo e tabulazione sono caratteri normali: restano
    assert pulisci_testo("Ștefan è qui 😀") == "Ștefan è qui 😀"    # Accenti ed emoji intere restano


def test_indirizzo_con_interno_e_scala():
    # Prima "scala B" veniva scambiato per il comune, e Milano spariva diventando solo la sigla MI
    assert sistema_indirizzo("via roma 10 int. 4 scala b milano") == "Via Roma 10 int. 4 scala B, Milano"
    assert sistema_indirizzo("via roma 10 scala b milano") == "Via Roma 10 scala B, Milano"
    assert sistema_indirizzo("Via Roma 10, interno 4, Milano") == "Via Roma 10 interno 4, Milano"
    assert sistema_indirizzo("via roma 10 palazzina c robecco sul naviglio mi") == "Via Roma 10 palazzina C, Robecco sul Naviglio, MI"


def test_indirizzo_gia_sistemato_non_cambia_piu():
    # Chi corregge a mano un indirizzo già sistemato non deve vederselo cambiare di nuovo
    for indirizzo in ("Via Roma 10 int. 4 scala B, Milano", "Via Ponte 33, Robecco sul Naviglio, MI", "Viale 25 Aprile 4, Monza, MB"):
        assert sistema_indirizzo(indirizzo) == indirizzo
