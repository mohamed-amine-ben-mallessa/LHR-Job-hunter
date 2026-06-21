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
import os
import re
import unicodedata
from pathlib import Path

import cv_pdf
import telegram_notify
from cv_profile import ProfilError, load_profil


def _load_dotenv():
    """Charge un .env voisin (KEY=VALUE) sans écraser l'environnement existant."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def slugify(text, defaut="cv") -> str:
    """Nom de fichier sûr (Windows/Unix) depuis un texte : sans accents ni
    caractères spéciaux. Renvoie `defaut` si vide."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:60] or defaut


class OffreError(Exception):
    pass


# Métier -> (fichier profil, variable d'env de secours). "rang" et "serveur"
# partagent le profil par défaut. La variable d'env sert à GitHub Actions, où le
# profil.json (ignoré par git) n'existe pas : on le fournit via un secret.
PROFILS_METIER = {
    "rang": ("profil.json", "PROFIL_JSON"),
    "serveur": ("profil.json", "PROFIL_JSON"),
    "barman": ("profil.barman.json", "PROFIL_BARMAN_JSON"),
}


def resoudre_profil(profil_arg, metier_arg):
    """Renvoie (chemin_fichier, nom_var_env) du profil à charger.

    Priorité : --profil explicite > --metier > défaut (profil.json).
    `nom_var_env` est la variable de secours (secret) si le fichier manque ;
    None pour un --profil explicite.
    """
    if profil_arg:
        return profil_arg, None
    if metier_arg:
        return PROFILS_METIER[metier_arg]
    return "profil.json", "PROFIL_JSON"


def materialiser_profil(path, env_var):
    """Si `path` n'existe pas mais que la variable d'env `env_var` contient un
    JSON, écrit ce JSON dans `path`. Permet à GitHub Actions de fournir le
    profil via un secret. Sans effet si le fichier existe déjà."""
    if env_var and not Path(path).exists():
        contenu = os.environ.get(env_var, "").strip()
        if contenu:
            Path(path).write_text(contenu, encoding="utf-8")


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
    p.add_argument("--metier", choices=sorted(PROFILS_METIER),
                   help="Choisit le profil selon le métier (rang|serveur -> "
                        "profil.json ; barman -> profil.barman.json).")
    p.add_argument("--profil", default=None,
                   help="Fichier profil candidat (prioritaire sur --metier ; "
                        "défaut profil.json).")
    p.add_argument("--source", default="offres_24h.json",
                   help="Fichier JSON du dernier scrape (défaut offres_24h.json).")
    p.add_argument("--sortie", default="",
                   help="Chemin du PDF (défaut cv_<entreprise>.pdf).")
    p.add_argument("--telegram", action="store_true",
                   help="Envoie le CV PDF sur le canal Telegram configuré.")
    args = p.parse_args(argv)

    _load_dotenv()

    profil_path, env_var = resoudre_profil(args.profil, args.metier)
    # GitHub Actions : recrée le profil depuis un secret si le fichier manque.
    materialiser_profil(profil_path, env_var)
    try:
        profil = load_profil(profil_path)
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

    if args.telegram:
        cible = f"{titre} — {ent}" if ent else titre
        try:
            telegram_notify.send_document(
                sortie, caption=f"📄 CV — Candidature : {cible}")
            print("CV envoyé sur Telegram.")
        except telegram_notify.TelegramError as e:
            print(f"ERREUR Telegram : {e}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
