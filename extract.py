"""Logique pure : fraîcheur 24h, ciblage métier, détection du mode de candidature.

Aucune dépendance réseau ; tout est testable en isolation.
"""

import re
import unicodedata
from datetime import datetime, timedelta

# Date+heure produite par le scraper, ex : "21/06/2026 à 13:58:59".
_DT_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})(?:\s*à\s*(\d{2}):(\d{2}):(\d{2}))?")

MARQUEUR_SANS_DATE = "date inconnue"


def _norm(s: str) -> str:
    """Minuscule sans accents, pour comparer du texte sans se soucier de la casse."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def parse_datetime_fr(date_heure: str):
    """Parse "JJ/MM/AAAA à HH:MM:SS" -> datetime. Date seule -> 00:00:00.

    Renvoie None si vide, marqueur "date inconnue", ou non parsable.
    """
    s = (date_heure or "").strip()
    if not s or s == MARQUEUR_SANS_DATE:
        return None
    m = _DT_RE.search(s)
    if not m:
        return None
    d, mo, y, hh, mm, ss = m.groups()
    try:
        return datetime(int(y), int(mo), int(d),
                        int(hh or 0), int(mm or 0), int(ss or 0))
    except ValueError:
        return None


def is_within_24h(date_heure: str, now: datetime, heures: int = 24) -> bool:
    """True si l'offre est publiée il y a <= `heures`.

    `now` est injecté (testable). Un léger décalage dans le futur (horloge du
    serveur) est toléré. Une date absente -> False (géré à part par l'appelant).
    """
    dt = parse_datetime_fr(date_heure)
    if dt is None:
        return False
    delta = now - dt
    # Futur proche toléré (jusqu'à 1h d'avance) ; sinon <= fenêtre.
    return timedelta(hours=-1) <= delta <= timedelta(hours=heures)


# Intitulés ciblés (périmètre "élargi salle") et exclusions prioritaires.
_INCLURE = ("serveur", "serveuse", "chef de rang", "barman", "barmaid",
            "runner", "commis de salle")
_EXCLURE = ("cuisine", "plongeur", "chef de cuisine", "commis de cuisine",
            "patissier", "responsable de salle", "directeur", "maitre d")


def matches_metier(titre: str) -> bool:
    """True si le titre vise un poste de service en salle ciblé.

    Les exclusions priment : "Responsable de salle" est écarté même s'il
    contient "salle" ; "Commis de salle / Runner" est gardé.
    """
    t = _norm(titre)
    if any(x in t for x in _EXCLURE):
        return False
    return any(x in t for x in _INCLURE)


# Formules explicites de candidature sur place (déplacement avec CV).
# Volontairement étroit : ne doit PAS matcher le marketing "Venez rejoindre".
_SUR_PLACE_RES = [
    re.compile(p) for p in (
        r"(?:se|vous|nous) presenter",       # "se présenter", "vous présenter"
        r"presentez[ -]?vous",               # "présentez-vous", "présentez vous"
        r"deposer (?:votre |le |son )?cv",
        r"cv a l accueil",
        r"directement a l adresse",
        r"passer (?:nous )?(?:voir|deposer)",
        r"ven(?:ir|ez) avec (?:votre |un )?cv",
    )
]


def detect_candidature(description: str, email: str, telephone: str) -> str:
    """Mode de candidature souhaité.

    "sur place" prime si une formule explicite de déplacement est détectée.
    Sinon on déduit du canal disponible (email / téléphone).
    """
    d = _norm(description)
    if any(r.search(d) for r in _SUR_PLACE_RES):
        return "sur place"
    has_mail = bool((email or "").strip())
    has_tel = bool((telephone or "").strip())
    if has_mail and has_tel:
        return "email+telephone"
    if has_mail:
        return "email"
    if has_tel:
        return "telephone"
    return "non precise"
