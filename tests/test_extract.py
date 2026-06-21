"""Tests purs (sans réseau) de la logique d'extraction et de validation."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extract import (MARQUEUR_SANS_DATE, detect_candidature, extract_contrat,
                     extract_heures, extract_profil, extract_salaire,
                     is_within_24h, matches_metier, parse_datetime_fr,
                     refuse_deplacement)
from models import Offre
import lhr_scraper


# ── parse_datetime_fr ────────────────────────────────────────────────────────

def test_parse_date_heure_complete():
    dt = parse_datetime_fr("21/06/2026 à 13:58:59")
    assert dt == datetime(2026, 6, 21, 13, 58, 59)


def test_parse_date_seule():
    dt = parse_datetime_fr("20/06/2026")
    assert dt == datetime(2026, 6, 20, 0, 0, 0)


def test_parse_vide_et_marqueur():
    assert parse_datetime_fr("") is None
    assert parse_datetime_fr(MARQUEUR_SANS_DATE) is None


def test_parse_invalide():
    assert parse_datetime_fr("pas une date") is None


# ── is_within_24h ────────────────────────────────────────────────────────────

NOW = datetime(2026, 6, 21, 14, 0, 0)


def _il_y_a(td):
    d = NOW - td
    return d.strftime("%d/%m/%Y à %H:%M:%S")


def test_within_maintenant():
    assert is_within_24h(_il_y_a(timedelta(0)), NOW) is True


def test_within_23h59():
    assert is_within_24h(_il_y_a(timedelta(hours=23, minutes=59)), NOW) is True


def test_within_24h01_exclu():
    assert is_within_24h(_il_y_a(timedelta(hours=24, minutes=1)), NOW) is False


def test_within_futur_proche_tolere():
    futur = (NOW + timedelta(minutes=30)).strftime("%d/%m/%Y à %H:%M:%S")
    assert is_within_24h(futur, NOW) is True


def test_within_vide():
    assert is_within_24h("", NOW) is False


def test_within_fenetre_personnalisee():
    il_y_a_40h = _il_y_a(timedelta(hours=40))
    assert is_within_24h(il_y_a_40h, NOW, heures=24) is False
    assert is_within_24h(il_y_a_40h, NOW, heures=48) is True


# ── matches_metier ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("titre", [
    "Serveur H/F",
    "Serveuse",
    "Chef de rang H/F",
    "Barman(maid)",
    "Commis de salle / Runner H/F",
    "RUNNER H/F",
])
def test_metier_inclus(titre):
    assert matches_metier(titre) is True


@pytest.mark.parametrize("titre", [
    "Responsable de salle H/F",
    "Directeur de salle",
    "Maître d'hôtel",
    "Chef de cuisine H/F",
    "Commis de cuisine",
    "Plongeur H/F",
    "Pâtissier",
])
def test_metier_exclu(titre):
    assert matches_metier(titre) is False


# ── detect_candidature ───────────────────────────────────────────────────────

def test_candidature_sur_place():
    d = "Poste à pourvoir. Merci de vous présenter au 12 rue X avec votre CV."
    assert detect_candidature(d, "", "") == "sur place"


def test_candidature_deposer_cv():
    d = "Venir déposer votre CV directement à l'accueil du restaurant."
    assert detect_candidature(d, "", "") == "sur place"


def test_candidature_venez_rejoindre_pas_sur_place():
    # « Venez rejoindre » est du marketing, pas une consigne de déplacement.
    d = "Venez rejoindre notre équipe dynamique et passionnée !"
    assert detect_candidature(d, "contact@resto.fr", "") == "email"


def test_candidature_passez_nous_rencontrer():
    # Cas réel raté avant : "passez directement nous rencontrer au café".
    d = "Candidature : ou passez directement nous rencontrer au café !"
    assert detect_candidature(d, "x@y.fr", "") == "sur place"


def test_candidature_venez_nous_voir():
    assert detect_candidature("Venez nous voir au restaurant", "", "") == "sur place"


def test_candidature_negation_force_email():
    # "Ne pas se déplacer" NE doit PAS donner "sur place".
    d = "Candidatures uniquement par mail. Ne pas téléphoner ni se déplacer."
    assert detect_candidature(d, "x@y.fr", "06 81 77 46 26") == "email+telephone"
    assert refuse_deplacement(d) is True


def test_candidature_negation_meme_avec_formule_deplacement():
    # Même si une formule de déplacement traîne, la négation prime.
    d = "Se présenter… non : ne pas se déplacer, candidature uniquement par mail."
    assert detect_candidature(d, "x@y.fr", "") == "email"


def test_refuse_deplacement_faux_quand_absent():
    assert refuse_deplacement("Venez nous rencontrer au café") is False


def test_candidature_email_seul():
    assert detect_candidature("Envoyer votre CV", "x@y.fr", "") == "email"


def test_candidature_tel_seul():
    assert detect_candidature("Appelez-nous", "", "06 81 77 46 26") == "telephone"


def test_candidature_email_et_tel():
    assert detect_candidature("", "x@y.fr", "06 81 77 46 26") == "email+telephone"


def test_candidature_non_precise():
    assert detect_candidature("Description sans coordonnées", "", "") == "non precise"


# ── models.Offre (validation Pydantic) ───────────────────────────────────────

def test_offre_telephone_valide_conserve():
    o = Offre(titre="Serveur H/F", telephone="06 81 77 46 26",
              candidature="telephone", url="http://x")
    assert o.telephone == "06 81 77 46 26"


def test_offre_telephone_parasite_rejete():
    # 10 chiffres mais pas un format de tél FR normalisé -> écarté.
    o = Offre(titre="Serveur H/F", telephone="1234567890",
              candidature="non precise", url="http://x")
    assert o.telephone == ""


def test_offre_email_valide_conserve():
    o = Offre(titre="Serveur H/F", email="contact@resto.fr",
              candidature="email", url="http://x")
    assert o.email == "contact@resto.fr"


def test_offre_email_image_rejete():
    o = Offre(titre="Serveur H/F", email="logo@2x.png",
              candidature="non precise", url="http://x")
    assert o.email == ""


def test_offre_candidature_invalide_leve():
    with pytest.raises(Exception):
        Offre(titre="x", candidature="par pigeon voyageur", url="http://x")


def test_offre_row_ordre_colonnes():
    o = Offre(titre="Serveur H/F", candidature="non precise", url="http://x")
    row = o.row()
    assert list(row.keys()) == [
        "titre", "entreprise", "lieu", "code_postal", "date_heure",
        "telephone", "email", "candidature", "note", "contrat", "salaire",
        "heures", "profil", "url",
    ]


# ── telegram_notify (formatage, sans réseau) ─────────────────────────────────

import telegram_notify as tg


def test_tg_format_offre_contient_titre_et_lien():
    o = Offre(titre="Chef de rang H/F", entreprise="Quai Ouest",
              telephone="06 81 77 46 26", candidature="telephone",
              url="https://x/1")
    bloc = tg.format_offre(o)
    assert "<b>Chef de rang H/F</b>" in bloc
    assert "Quai Ouest" in bloc
    assert "06 81 77 46 26" in bloc
    assert 'href="https://x/1"' in bloc


def test_tg_escape_html():
    o = Offre(titre="Serveur <Top> & Co", candidature="non precise",
              url="https://x/2")
    bloc = tg.format_offre(o)
    assert "&lt;Top&gt;" in bloc and "&amp;" in bloc


def test_tg_build_messages_decoupe_si_trop_long():
    # Beaucoup d'offres -> dépasse la limite -> plusieurs messages.
    offres = [Offre(titre=f"Serveur {i} H/F", entreprise="X" * 200,
                    candidature="non precise", url=f"https://x/{i}")
              for i in range(60)]
    msgs = tg.build_messages(offres, "entete")
    assert len(msgs) >= 2
    assert all(len(m) <= 4096 for m in msgs)


def test_tg_send_document_fichier_absent_ne_leve_pas():
    # Best-effort : un chemin inexistant renvoie False sans appeler le réseau.
    assert tg.send_document("/chemin/inexistant.csv",
                            token="x", chat_id="y") is False


def test_tg_format_offre_affiche_nouveaux_champs():
    o = Offre(titre="Serveur H/F", candidature="email", contrat="CDI",
              salaire="2000€ net", heures="39h hebdo",
              profil="Expérimenté, dynamique", url="https://x/1")
    bloc = tg.format_offre(o)
    assert "CDI" in bloc and "39h hebdo" in bloc
    assert "2000€ net" in bloc and "Profil" in bloc


# ── extract_salaire ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("desc,doit_contenir", [
    ("De 1700€ à 2100€ net mensuel", "1700€"),
    ("Rémunération : 2 700 € net par mois", "2 700 €"),
    ("à partir de 2000€ nets, ajustable", "2000€"),
    ("Salaire entre 2 500 & 2 800€ Net selon", "2 800€"),
])
def test_extract_salaire(desc, doit_contenir):
    out = extract_salaire(desc)
    assert "€" in out and doit_contenir in out


def test_extract_salaire_aucun():
    assert extract_salaire("Poste sympa, équipe au top.") == ""


# ── extract_heures ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("desc,attendu", [
    ("temps complet 169H mensuel, service", "169H mensuel"),
    ("Serveur 30H par semaine", "30H par semaine"),
    ("CDI, 39 Heures hebdo, journées", "39 Heures hebdo"),
])
def test_extract_heures(desc, attendu):
    assert extract_heures(desc) == attendu


def test_extract_heures_ignore_horaire_service():
    # "7h/16h" est une plage horaire, pas un volume -> pas capturé.
    assert extract_heures("service le matin 7h/16h (+/-1h)") == ""


# ── extract_contrat ──────────────────────────────────────────────────────────

def test_extract_contrat_cdi():
    assert extract_contrat("Poste en CDI à pourvoir") == "CDI"


def test_extract_contrat_multiple():
    out = extract_contrat("Contrat : CDI / CDD/ saisonnier")
    assert "CDI" in out and "CDD" in out and "Saisonnier" in out


def test_extract_contrat_aucun():
    assert extract_contrat("Rejoignez notre équipe !") == ""


# ── extract_profil ───────────────────────────────────────────────────────────

def test_extract_profil_section():
    desc = ("Missions : servir.\nProfil recherché :\n"
            "Expérience exigée\nBonne présentation\n"
            "Conditions :\nCDI")
    out = extract_profil(desc)
    assert "Expérience exigée" in out and "Bonne présentation" in out
    assert "Conditions" not in out  # coupé au prochain en-tête


def test_extract_profil_absent():
    assert extract_profil("Description sans section profil.") == ""


# ── téléphone : formats variés (lhr_scraper) ─────────────────────────────────

@pytest.mark.parametrize("texte,attendu", [
    ("Appelez le 06 81 77 46 26", "06 81 77 46 26"),
    ("tel 06.81.77.46.26", "06 81 77 46 26"),
    ("au 06-81-77-46-26", "06 81 77 46 26"),
    ("direct 0681774626 svp", "06 81 77 46 26"),
    ("au +33 6 81 77 46 26", "06 81 77 46 26"),
    ("fixe 01 43 29 88 27", "01 43 29 88 27"),
])
def test_phone_formats_varies(texte, attendu):
    assert lhr_scraper._first_phone(texte) == attendu


def test_phone_rejette_faux_positifs():
    assert lhr_scraper._first_phone("prix 1596.40 euros") == ""
    assert lhr_scraper._first_phone("SIRET 12345678901234") == ""
