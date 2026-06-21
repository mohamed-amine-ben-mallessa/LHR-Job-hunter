"""CLI — Offres Salle/Bar Île-de-France des dernières 24h.

Scrape les offres de service en salle (serveur, chef de rang, barman, runner,
commis de salle) récentes en Île-de-France sur lhotellerie-restauration.fr,
extrait téléphone / email / mode de candidature, et écrit un CSV + un JSON.

Usage :
    python scrape_24h.py [--max N] [--heures H] [--sortie PREFIXE]
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import asyncio
import csv
import json
import os
from datetime import datetime

import lhr_scraper
import telegram_notify
from extract import (MARQUEUR_SANS_DATE, detect_candidature, is_within_24h,
                     matches_metier, parse_datetime_fr)
from models import COLUMNS, Offre

REGION = "ile-de-france"
METIER = "salle-bar-cafe-room-service"


def _load_dotenv():
    """Charge un fichier .env voisin (KEY=VALUE) dans l'environnement, sans
    écraser les variables déjà définies. Pas de dépendance externe."""
    from pathlib import Path

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


def _filet_coordonnees(offre: dict):
    """Complète téléphone / email depuis la description si le détail les a ratés.

    Les coordonnées sont souvent en fin de description, après « Envoyer votre
    CV à … ». On ne réécrit jamais une valeur déjà présente.
    """
    desc = offre.get("description", "") or ""
    if not offre.get("telephone"):
        offre["telephone"] = lhr_scraper._first_phone(desc)
    if not offre.get("email"):
        offre["email"] = (lhr_scraper._decode_icon2_email(desc)
                          or lhr_scraper._first_email(desc))


def _to_offre(raw: dict, date_affichee: str) -> Offre:
    """Construit un Offre Pydantic (validé) depuis l'offre brute scrapée."""
    candidature = detect_candidature(
        raw.get("description", ""), raw.get("email", ""), raw.get("telephone", ""))
    return Offre(
        titre=raw.get("titre", ""),
        entreprise=raw.get("entreprise", ""),
        lieu=raw.get("lieu", ""),
        code_postal=raw.get("code_postal", ""),
        date_heure=date_affichee,
        telephone=raw.get("telephone", ""),
        email=raw.get("email", ""),
        candidature=candidature,
        salaire=raw.get("salaire", ""),
        url=raw.get("url", ""),
    )


def _sort_key(o: Offre):
    """Tri par date décroissante ; offres sans date renvoyées en fin."""
    dt = parse_datetime_fr(o.date_heure)
    return (0, datetime.min) if dt is None else (1, dt)


def filtrer(raw_offres, now, heures):
    """Applique métier + fraîcheur 24h ; renvoie (offres Pydantic triées, nb_sans_date)."""
    gardees = []
    sans_date = 0
    for raw in raw_offres:
        if not matches_metier(raw.get("titre", "")):
            continue
        date_heure = raw.get("date_heure", "") or ""
        dt = parse_datetime_fr(date_heure)
        if dt is None:
            # Sans date : on garde et on marque (décision « inclure + marquer »).
            sans_date += 1
            date_affichee = MARQUEUR_SANS_DATE
        elif is_within_24h(date_heure, now, heures):
            date_affichee = date_heure
        else:
            continue
        _filet_coordonnees(raw)
        gardees.append(_to_offre(raw, date_affichee))
    # Sans date en dernier, récentes en premier.
    gardees.sort(key=_sort_key, reverse=True)
    return gardees, sans_date


def ecrire_sorties(offres, prefixe):
    """Écrit <prefixe>.csv (UTF-8 BOM, pour Excel) et <prefixe>.json."""
    rows = [o.row() for o in offres]
    csv_path = f"{prefixe}.csv"
    json_path = f"{prefixe}.json"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return csv_path, json_path


async def _run_async(args) -> int:
    # 1er message : accusé rapide, AVANT le scrape, pour avoir un signe de vie
    # même si le scraping est lent.
    if args.telegram:
        _envoyer_accuse(args.heures)

    print(f"Scraping Salle/Bar Île-de-France (max {args.max} offres)…")
    try:
        raw_offres = await lhr_scraper.scrape(
            region=REGION, metier=METIER, max_offres=args.max,
            on_event=lambda m: print(f"  {m}"))
    except Exception as e:  # échec global du scrape
        print(f"ERREUR : le scraping a échoué ({e}).", file=sys.stderr)
        if args.telegram:
            _envoyer_erreur(e)
        return 1

    now = datetime.now()
    offres, sans_date = filtrer(raw_offres, now, args.heures)
    csv_path, json_path = ecrire_sorties(offres, args.sortie)

    print()
    print(f"{len(offres)} offres gardées (dont {sans_date} sans date) "
          f"sur {len(raw_offres)} scrapées.")
    print(f"  -> {csv_path}")
    print(f"  -> {json_path}")
    # Aperçu rapide.
    for o in offres[:10]:
        coord = o.telephone or o.email or "—"
        print(f"  • {o.titre} | {o.entreprise} | {o.date_heure} "
              f"| {o.candidature} | {coord}")

    # 2e message : le résultat complet + le CSV joint.
    if args.telegram:
        _envoyer_resultat(offres, args.heures, csv_path)
    return 0


def _envoyer_accuse(heures):
    """1er message : accusé de lancement (signe de vie immédiat)."""
    today = datetime.now().strftime("%d/%m/%Y à %H:%M")
    txt = (f"⏳ <b>Recherche d'offres Salle/Bar Île-de-France</b> "
           f"(&lt;{heures}h) en cours… — {today}")
    try:
        telegram_notify.send_text(txt)
    except telegram_notify.TelegramError as e:
        # L'accusé est best-effort : on ne bloque pas le run s'il échoue.
        print(f"ATTENTION : accusé Telegram non envoyé ({e}).", file=sys.stderr)


def _envoyer_resultat(offres, heures, csv_path):
    """2e message : les offres + le CSV joint."""
    today = datetime.now().strftime("%d/%m/%Y")
    if offres:
        entete = (f"🍽️ <b>Offres Salle/Bar Île-de-France</b> "
                  f"({len(offres)} offre(s), &lt;{heures}h) — {today}")
    else:
        entete = (f"🍽️ <b>Offres Salle/Bar Île-de-France</b> — {today}\n"
                  f"Aucune offre dans les {heures} dernières heures.")
    try:
        messages = telegram_notify.build_messages(offres, entete)
        sent = telegram_notify.send(messages)
        # Joindre le CSV s'il y a des offres.
        if offres:
            telegram_notify.send_document(
                csv_path, caption=f"CSV — {len(offres)} offre(s), {today}")
        print(f"Telegram : {sent} message(s) + CSV envoyés.")
    except telegram_notify.TelegramError as e:
        print(f"ERREUR Telegram : {e}", file=sys.stderr)
        return 2
    return 0


def _envoyer_erreur(exc):
    """Notifie un échec de scraping sur le canal (best-effort)."""
    try:
        telegram_notify.send_text(
            f"❌ Le scraping a échoué : {telegram_notify._escape(str(exc))[:300]}")
    except telegram_notify.TelegramError:
        pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offres Salle/Bar Île-de-France des dernières 24h "
                    "(serveur, chef de rang, barman, runner, commis de salle).")
    p.add_argument("--max", type=int, default=120,
                   help="Nombre max d'offres scrapées en amont (défaut 120).")
    p.add_argument("--heures", type=int, default=24,
                   help="Fenêtre de fraîcheur en heures (défaut 24).")
    p.add_argument("--sortie", default="offres_24h",
                   help="Préfixe des fichiers de sortie (défaut 'offres_24h').")
    p.add_argument("--telegram", action="store_true",
                   help="Envoyer les offres sur le canal Telegram configuré "
                        "(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
    args = p.parse_args(argv)
    _load_dotenv()
    return asyncio.run(_run_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
