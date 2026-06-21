"""Schémas Pydantic — source de vérité du format de sortie.

La couche Pydantic valide et structure chaque offre : elle rejette les faux
numéros / emails et contraint le champ `candidature` à un ensemble fixe de
valeurs. Le CSV et le JSON sont sérialisés depuis ces objets validés.
"""

import re
from typing import Literal

from pydantic import BaseModel, field_validator

# Colonnes de sortie, dans l'ordre (CSV + clés JSON).
COLUMNS = [
    "titre", "entreprise", "lieu", "code_postal", "date_heure",
    "telephone", "email", "candidature", "note", "contrat", "salaire",
    "heures", "profil", "url",
]

Candidature = Literal[
    "sur place", "email", "telephone", "email+telephone", "non precise",
]

# Téléphone FR normalisé : "06 81 77 46 26" (5 paires séparées par un espace).
_PHONE_NORM_RE = re.compile(r"^0[1-9](?: \d{2}){4}$")
# Email simple mais strict (un seul @, domaine avec point, TLD alphabétique).
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
# Faux emails fréquents (images, domaines techniques du site).
_EMAIL_SKIP = ("lhotellerie-restauration", "sentry", "example.", "@2x",
               ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


class Offre(BaseModel):
    """Une offre d'emploi validée, prête à sérialiser."""

    titre: str
    entreprise: str = ""
    lieu: str = ""
    code_postal: str = ""
    date_heure: str = ""          # "JJ/MM/AAAA à HH:MM:SS", ou "date inconnue"
    telephone: str = ""           # 10 chiffres FR formatés, sinon ""
    email: str = ""               # format email valide, sinon ""
    candidature: Candidature = "non precise"
    note: str = ""                # ex. "ne pas se déplacer" (consigne de l'annonce)
    contrat: str = ""             # ex. "CDI", "CDD / Saisonnier"
    salaire: str = ""
    heures: str = ""              # ex. "169H mensuel", "39h hebdo"
    profil: str = ""              # texte de la section "Profil recherché"
    url: str

    @field_validator("telephone")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        """Ne garde que les vrais numéros FR déjà normalisés ; "" sinon.

        Le scraper normalise en paires "06 81 77 46 26". Tout ce qui ne colle
        pas à ce format (montant, SIRET, fragment) est écarté.
        """
        v = (v or "").strip()
        return v if _PHONE_NORM_RE.match(v) else ""

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        """Valide le format et écarte les faux positifs (images, domaines site)."""
        v = (v or "").strip()
        if not _EMAIL_RE.match(v):
            return ""
        low = v.lower()
        if any(skip in low for skip in _EMAIL_SKIP):
            return ""
        return v

    def row(self) -> dict:
        """Dict ordonné selon COLUMNS, pour CSV / JSON."""
        d = self.model_dump()
        return {k: d.get(k, "") for k in COLUMNS}
