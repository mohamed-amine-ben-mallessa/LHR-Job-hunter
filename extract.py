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
# Volontairement précis : ne doit PAS matcher le marketing "Venez rejoindre".
# (Textes normalisés : sans accents, en minuscules.)
_SUR_PLACE_RES = [
    re.compile(p) for p in (
        r"(?:se|vous|nous) presenter",            # "se présenter", "vous présenter"
        r"presentez[ -]?vous",                    # "présentez-vous"
        r"deposer (?:votre |le |son )?cv",        # "déposer votre CV"
        r"cv a l accueil",
        r"directement a l adresse",
        r"passe[rz] (?:nous |directement )?(?:nous )?(?:voir|deposer|rencontrer)",
        r"venez (?:nous )?(?:voir|rencontrer)",   # "passez/venez nous rencontrer"
        r"ven(?:ir|ez) avec (?:votre |un )?cv",
        r"candidature (?:uniquement )?sur place",
        r"depose[rz] (?:votre |le )?(?:cv|candidature) (?:au|a|sur place|directement)",
        r"rencontrer (?:nous|l equipe) (?:au|directement|sur place)",
    )
]

# Négation explicite : le resto REFUSE le déplacement / les appels.
# Si détectée, elle annule "sur place" et force le canal email.
_NE_PAS_DEPLACER_RES = [
    re.compile(p) for p in (
        r"ne pas (?:se )?deplac",                 # "ne pas se déplacer"
        r"sans (?:vous )?deplac",                 # "sans vous déplacer"
        r"pas de presentation",
        r"ne pas (?:nous )?telephoner",
        r"uniquement par (?:mail|courriel|e-?mail)",
        r"candidature[s]? uniquement par",
    )
]


def refuse_deplacement(description: str) -> bool:
    """True si l'annonce demande explicitement de NE PAS se déplacer/téléphoner."""
    d = _norm(description)
    return any(r.search(d) for r in _NE_PAS_DEPLACER_RES)


def detect_candidature(description: str, email: str, telephone: str) -> str:
    """Mode de candidature souhaité.

    Priorité : si l'annonce interdit le déplacement ("ne pas se déplacer",
    "uniquement par mail"), on ne renvoie JAMAIS "sur place" — on déduit le
    canal (email/téléphone). Sinon, "sur place" prime dès qu'une formule
    explicite de déplacement est détectée.
    """
    d = _norm(description)
    interdit = refuse_deplacement(description)
    if not interdit and any(r.search(d) for r in _SUR_PLACE_RES):
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


# ── Salaire (depuis le texte de la description) ──────────────────────────────
# Le JSON-LD ne porte pas toujours le salaire ; il est souvent écrit en clair :
#   "De 1700€ à 2100€ net mensuel", "2 700 € net par mois",
#   "à partir de 2000€ nets", "35,9K€", "1596.40€ BRUT", "entre 2 500 & 2 800€".
# Un montant = chiffres avec espaces/points/virgules comme séparateurs, suivi
# (ou précédé) d'un € et éventuellement d'un "K".
_MONTANT = r"\d[\d  .,]*\s?[kK]?\s?€"
_SALAIRE_RES = [
    # Fourchette : "De 1700€ à 2100€ …", "entre 2 500 & 2 800€ …"
    re.compile(r"(?:de|entre)\s+" + _MONTANT + r"\s*(?:à|a|&|-|et)\s*" + _MONTANT
               + r"[^\n.;]{0,40}", re.I),
    # "à partir de 2000€ …"
    re.compile(r"(?:à|a)\s+partir\s+de\s+" + _MONTANT + r"[^\n.;]{0,40}", re.I),
    # Préfixé par un mot-clé : "Rémunération : 2 700 € net…", "Salaire : 1596€…"
    re.compile(r"(?:r[ée]mun[ée]ration|salaire)\s*:?[^\n€]{0,20}" + _MONTANT
               + r"[^\n.;]{0,40}", re.I),
    # Montant isolé suivi d'une qualif (net/brut/mensuel…) : "2000€ nets"
    re.compile(_MONTANT + r"\s*(?:net|nets|brut|bruts|mensuel|/\s?mois|par\s+mois)"
               r"[^\n.;]{0,30}", re.I),
    # "à partir de 35,9K€ + pourboires" — on coupe avant "Avantages/Avantage".
    re.compile(r"(?:à|a)\s+partir\s+de\s+" + _MONTANT
               + r"[^\n.;]*?(?=\s+avantages?\b|[\n.;]|$)", re.I),
    # Dernier recours : tout montant avec € (le plus court contexte).
    re.compile(_MONTANT, re.I),
]


def _clean_inline(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip(" -:•·.")


def extract_salaire(description: str) -> str:
    """Premier salaire plausible trouvé dans la description, sinon "".

    Renvoie le segment lisible (ex. "De 1700€ à 2100€ net mensuel"). Les regex
    sont essayées de la plus spécifique (fourchette) à la plus large.
    """
    text = description or ""
    for rgx in _SALAIRE_RES:
        m = rgx.search(text)
        if m:
            return _clean_inline(m.group(0))
    return ""


# ── Volume horaire ───────────────────────────────────────────────────────────
# "169H mensuel", "39h hebdo", "30H par semaine", "39 Heures hebdo", "39h/42h".
# On ne veut PAS les horaires de service type "7h/16h" : on exige un volume
# (>=30 typiquement, ou un mot "semaine/mois/hebdo/mensuel" à proximité).
_HEURES_RES = [
    re.compile(r"\d{2,3}\s?[hH](?:eures?)?\s?(?:/\s?\d{2,3}\s?[hH])?\s*"
               r"(?:par\s+)?(?:semaine|mois|hebdo\w*|mensuel\w*)", re.I),
    re.compile(r"\d{2,3}\s?[hH](?:eures?)?\s?(?:par\s+)?"
               r"(?:semaine|mois|hebdo\w*|mensuel\w*)", re.I),
]


def extract_heures(description: str) -> str:
    """Volume horaire (ex. "169H mensuel", "39h hebdo"), sinon "".

    Évite les plages horaires de service (7h/16h) en exigeant un mot de
    périodicité (semaine/mois/hebdo/mensuel).
    """
    text = description or ""
    for rgx in _HEURES_RES:
        m = rgx.search(text)
        if m:
            return _clean_inline(m.group(0))
    return ""


# ── Type de contrat ──────────────────────────────────────────────────────────
_CONTRAT_PATTERNS = [
    ("CDI", r"\bcdi\b"),
    ("CDD", r"\bcdd\b"),
    ("Saisonnier", r"saisonnier"),
    ("Extra", r"\bextras?\b"),
    ("Apprentissage", r"apprentissage|contrat\s+pro|alternance"),
    ("Stage", r"\bstage\b|stagiaire"),
    ("Intérim", r"int[ée]rim"),
]
_CONTRAT_RES = [(label, re.compile(pat, re.I)) for label, pat in _CONTRAT_PATTERNS]


def extract_contrat(description: str) -> str:
    """Type(s) de contrat détecté(s) dans le texte (ex. "CDI", "CDD / Saisonnier").

    Renvoie les libellés trouvés joints par " / ", sinon "".
    """
    d = _norm(description)
    found = [label for label, rgx in _CONTRAT_RES if rgx.search(d)]
    return " / ".join(found)


# ── Section "Profil recherché" ───────────────────────────────────────────────
# Le bloc commence à "Profil recherché" et court jusqu'au prochain en-tête
# fréquent (Conditions, Missions, Rémunération, Salaire, Contrat, Type…) ou la
# fin du texte.
_PROFIL_START_RE = re.compile(r"profil\s+recherch[ée]\s*:?", re.I)
_PROFIL_END_RE = re.compile(
    r"\n\s*(?:conditions?|missions?|r[ée]mun[ée]ration|salaire|"
    r"type\s+de\s+contrat|contrat|horaires?|avantages?|nous\s+offrons|"
    r"poste\s+[àa]\s+pourvoir|envoy(?:er|ez)|merci\s+de)\b", re.I)


def extract_profil(description: str) -> str:
    """Texte de la section 'Profil recherché' s'il existe, sinon "".

    Démarre au libellé et s'arrête au prochain en-tête de section connu.
    Compacte les espaces multiples mais garde les retours à la ligne.
    """
    text = description or ""
    m = _PROFIL_START_RE.search(text)
    if not m:
        return ""
    reste = text[m.end():]
    fin = _PROFIL_END_RE.search(reste)
    bloc = reste[:fin.start()] if fin else reste
    bloc = re.sub(r"[ \t]+", " ", bloc)
    # Retire les lignes vides / puces orphelines en tête de bloc.
    bloc = re.sub(r"^(?:\s*[-*•/]?\s*\n)+", "", bloc)
    return bloc.strip(" -:*•/\n")
