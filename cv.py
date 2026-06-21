"""CLI — génère un CV PDF adapté à une offre du dernier scrape.

Usage :
    python cv.py --offre N [--profil profil.json] [--source offres_24h.json]
                 [--sortie cv.pdf]

N est l'index 1-based de l'offre dans offres_24h.json (même ordre que l'aperçu
affiché par scrape_24h.py).
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import re
import unicodedata
from pathlib import Path

import cv_pdf
from cv_profile import ProfilError, load_profil


def slugify(text, defaut="cv") -> str:
    """Nom de fichier sûr (Windows/Unix) depuis un texte : sans accents ni
    caractères spéciaux. Renvoie `defaut` si vide."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:60] or defaut


class OffreError(Exception):
    pass


def charger_offre(source, index_1based):
    """Renvoie l'offre n°index_1based depuis le JSON du scrape. Lève OffreError
    avec un message clair (source absente / index hors limites)."""
    p = Path(source)
    if not p.exists():
        raise OffreError(
            f"Aucun scrape trouvé ({source}). Lance d'abord "
            f"'python scrape_24h.py'.")
    try:
        offres = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise OffreError(f"Fichier d'offres illisible ({source}) : {e}")
    if not isinstance(offres, list) or not offres:
        raise OffreError(f"Aucune offre dans {source}.")
    n = len(offres)
    if index_1based < 1 or index_1based > n:
        raise OffreError(
            f"Offre {index_1based} inexistante (1–{n} disponibles).")
    return offres[index_1based - 1]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Génère un CV PDF adapté à une offre du dernier scrape.")
    p.add_argument("--offre", type=int, required=True,
                   help="Index 1-based de l'offre dans le fichier de scrape.")
    p.add_argument("--profil", default="profil.json",
                   help="Fichier profil candidat (défaut profil.json).")
    p.add_argument("--source", default="offres_24h.json",
                   help="Fichier JSON du dernier scrape (défaut offres_24h.json).")
    p.add_argument("--sortie", default="",
                   help="Chemin du PDF (défaut cv_<entreprise>.pdf).")
    args = p.parse_args(argv)

    try:
        profil = load_profil(args.profil)
    except ProfilError as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    try:
        offre = charger_offre(args.source, args.offre)
    except OffreError as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1

    sortie = args.sortie or f"cv_{slugify(offre.get('entreprise', ''))}.pdf"
    cv_pdf.build_cv(profil, offre, sortie)

    titre = offre.get("titre", "")
    ent = offre.get("entreprise", "")
    print(f"CV généré : {sortie}")
    print(f"  pour : {titre}" + (f" — {ent}" if ent else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
