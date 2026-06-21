"""Tests de la génération de CV PDF (sans réseau)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv
import cv_pdf
from cv_profile import Profil, ProfilError, load_profil


# ── slugify ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("entree,attendu", [
    ("Quai Ouest", "Quai-Ouest"),
    ("Café de Flore", "Cafe-de-Flore"),
    ("LAUGO / Brasserie", "LAUGO-Brasserie"),
    ("  ", "cv"),            # vide -> défaut
    ("", "cv"),
])
def test_slugify(entree, attendu):
    assert cv.slugify(entree) == attendu


# ── profile.load_profil ──────────────────────────────────────────────────────

def _ecrire(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_load_profil_valide(tmp_path):
    path = _ecrire(tmp_path, "profil.json",
                   {"nom": "Jean Dupont", "titre": "Serveur"})
    prof = load_profil(path)
    assert prof.nom == "Jean Dupont" and prof.titre == "Serveur"


def test_load_profil_absent(tmp_path):
    with pytest.raises(ProfilError) as e:
        load_profil(str(tmp_path / "nope.json"))
    assert "introuvable" in str(e.value).lower()


def test_load_profil_json_invalide(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{pas du json", encoding="utf-8")
    with pytest.raises(ProfilError) as e:
        load_profil(str(p))
    assert "invalide" in str(e.value).lower()


def test_load_profil_champ_requis_manquant(tmp_path):
    path = _ecrire(tmp_path, "p.json", {"titre": "Serveur"})  # pas de nom
    with pytest.raises(ProfilError) as e:
        load_profil(path)
    assert "nom" in str(e.value)


# ── charger_offre ────────────────────────────────────────────────────────────

def test_charger_offre_index_valide(tmp_path):
    src = _ecrire(tmp_path, "o.json",
                  [{"titre": "A"}, {"titre": "B"}, {"titre": "C"}])
    assert cv.charger_offre(src, 2)["titre"] == "B"


def test_charger_offre_index_hors_limites(tmp_path):
    src = _ecrire(tmp_path, "o.json", [{"titre": "A"}])
    with pytest.raises(cv.OffreError) as e:
        cv.charger_offre(src, 5)
    assert "1–1" in str(e.value) or "1-1" in str(e.value)


def test_charger_offre_source_absente(tmp_path):
    with pytest.raises(cv.OffreError) as e:
        cv.charger_offre(str(tmp_path / "nope.json"), 1)
    assert "scrap" in str(e.value).lower()


# ── build_cv (PDF) ───────────────────────────────────────────────────────────

def _profil_complet():
    return Profil(
        nom="Jean Dupont", titre="Chef de rang", email="j@d.fr",
        telephone="06 12 34 56 78", ville="Paris",
        resume="Six ans d'expérience en brasserie.",
        experiences=[{"poste": "Chef de rang", "entreprise": "Le Bistrot",
                      "periode": "2022-2024", "lieu": "Paris",
                      "details": ["Service 80 couverts", "Accord mets-vins"]}],
        formations=[{"intitule": "CAP Restaurant", "etablissement": "Lycée",
                     "annee": "2019"}],
        competences=["Service", "Port de plateau"],
        langues=["Français", "Anglais"],
    )


def _est_pdf(path):
    data = Path(path).read_bytes()
    return data[:4] == b"%PDF" and len(data) > 800


def test_build_cv_genere_pdf(tmp_path):
    out = tmp_path / "cv.pdf"
    offre = {"titre": "Chef de rang H/F", "entreprise": "Quai Ouest",
             "lieu": "92 - Boulogne", "url": "https://x/1"}
    cv_pdf.build_cv(_profil_complet(), offre, out)
    assert _est_pdf(out)


def test_build_cv_profil_minimal(tmp_path):
    # Profil avec seulement le nom : sections vides omises, pas de crash.
    out = tmp_path / "cv_min.pdf"
    cv_pdf.build_cv(Profil(nom="Solo"), {"titre": "Serveur H/F"}, out)
    assert _est_pdf(out)


def test_build_cv_offre_sans_entreprise(tmp_path):
    # L'en-tête s'adapte si pas d'entreprise (pas de tiret orphelin).
    out = tmp_path / "cv2.pdf"
    cv_pdf.build_cv(_profil_complet(), {"titre": "Serveur H/F"}, out)
    assert _est_pdf(out)


def test_ligne_cible_vide_si_pas_de_titre():
    assert cv_pdf._ligne_cible({}) == ""
    assert cv_pdf._ligne_cible({"entreprise": "X"}) == ""


# ── resoudre_profil (--metier / --profil) ────────────────────────────────────

def test_resoudre_profil_defaut():
    assert cv.resoudre_profil(None, None)[0] == "profil.json"


@pytest.mark.parametrize("metier,attendu", [
    ("rang", "profil.json"),
    ("serveur", "profil.json"),
    ("barman", "profil.barman.json"),
])
def test_resoudre_profil_par_metier(metier, attendu):
    assert cv.resoudre_profil(None, metier)[0] == attendu


def test_resoudre_profil_explicite_prioritaire():
    # --profil l'emporte sur --metier.
    chemin, env_var = cv.resoudre_profil("autre.json", "barman")
    assert chemin == "autre.json" and env_var is None


def test_materialiser_profil_depuis_env(tmp_path, monkeypatch):
    # Si le fichier manque mais la variable d'env contient le JSON -> écrit.
    cible = tmp_path / "p.json"
    monkeypatch.setenv("PROFIL_TEST", '{"nom": "Depuis Secret"}')
    cv.materialiser_profil(str(cible), "PROFIL_TEST")
    assert cible.exists() and "Depuis Secret" in cible.read_text(encoding="utf-8")


def test_materialiser_profil_nexcrase_pas(tmp_path, monkeypatch):
    cible = tmp_path / "p.json"
    cible.write_text('{"nom": "Original"}', encoding="utf-8")
    monkeypatch.setenv("PROFIL_TEST", '{"nom": "Secret"}')
    cv.materialiser_profil(str(cible), "PROFIL_TEST")
    assert "Original" in cible.read_text(encoding="utf-8")  # pas écrasé
