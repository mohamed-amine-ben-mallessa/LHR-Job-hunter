"""Profil candidat : modèle Pydantic + chargement depuis profil.json.

Le profil est rempli une fois par l'utilisateur (voir profil.example.json). Il
sert de source unique pour générer le CV ; aucune IA n'intervient.
"""

import json
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field, ValidationError


class ProfilError(Exception):
    """Profil manquant ou invalide (message lisible pour l'utilisateur)."""


class Experience(BaseModel):
    poste: str = ""
    entreprise: str = ""
    periode: str = ""            # ex. "2022 – 2024"
    lieu: str = ""
    details: List[str] = Field(default_factory=list)


class Formation(BaseModel):
    intitule: str = ""
    etablissement: str = ""
    annee: str = ""


class Profil(BaseModel):
    """Profil candidat. Seul `nom` est requis ; le reste est optionnel et les
    sections vides sont simplement omises du PDF."""

    nom: str
    titre: str = ""              # ex. "Chef de rang"
    email: str = ""
    telephone: str = ""
    ville: str = ""
    resume: str = ""
    experiences: List[Experience] = Field(default_factory=list)
    formations: List[Formation] = Field(default_factory=list)
    competences: List[str] = Field(default_factory=list)
    langues: List[str] = Field(default_factory=list)


def load_profil(path="profil.json") -> Profil:
    """Charge et valide le profil. Lève ProfilError avec un message clair."""
    p = Path(path)
    if not p.exists():
        raise ProfilError(
            f"Profil introuvable : {path}. Copie 'profil.example.json' en "
            f"'{path}' et remplis-le.")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProfilError(f"Profil JSON invalide ({path}) : {e}")
    try:
        return Profil(**data)
    except ValidationError as e:
        # Première erreur lisible (ex. champ requis manquant).
        first = e.errors()[0]
        loc = ".".join(str(x) for x in first.get("loc", []))
        raise ProfilError(f"Profil invalide ({path}) — champ '{loc}': "
                          f"{first.get('msg', 'erreur')}")
