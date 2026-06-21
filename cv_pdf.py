"""Rendu du CV en PDF via ReportLab (pur Python, sans réseau).

`build_cv(profil, offre, sortie)` met en page le profil candidat avec un en-tête
ciblé sur l'offre. Les sections vides du profil sont omises.
"""

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Image, ListFlowable, ListItem,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

# Palette du template (un seul endroit pour ajuster le look).
ACCENT = colors.HexColor("#1f4e79")   # bleu profond
MUTED = colors.HexColor("#555555")


def _styles():
    base = getSampleStyleSheet()
    s = {}
    s["nom"] = ParagraphStyle("nom", parent=base["Title"], fontSize=20,
                              textColor=ACCENT, spaceAfter=2, leading=24,
                              alignment=TA_LEFT)
    s["titre"] = ParagraphStyle("titre", parent=base["Normal"], fontSize=12,
                                textColor=MUTED, spaceAfter=2)
    s["coord"] = ParagraphStyle("coord", parent=base["Normal"], fontSize=9,
                                textColor=MUTED, spaceAfter=6)
    s["cible"] = ParagraphStyle("cible", parent=base["Normal"], fontSize=10,
                                textColor=colors.white, backColor=ACCENT,
                                borderPadding=(6, 6, 6, 6), spaceBefore=4,
                                spaceAfter=10, leading=14)
    s["h2"] = ParagraphStyle("h2", parent=base["Heading2"], fontSize=12,
                             textColor=ACCENT, spaceBefore=10, spaceAfter=2)
    s["body"] = ParagraphStyle("body", parent=base["Normal"], fontSize=10,
                               leading=14, spaceAfter=2)
    s["exp_titre"] = ParagraphStyle("exp_titre", parent=base["Normal"],
                                    fontSize=10.5, leading=13, spaceBefore=4,
                                    spaceAfter=0)
    s["exp_meta"] = ParagraphStyle("exp_meta", parent=base["Normal"], fontSize=9,
                                   textColor=MUTED, spaceAfter=2)
    return s


def _esc(text) -> str:
    """Échappe le texte pour les Paragraph ReportLab (mini-markup XML)."""
    return (str(text or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _section_title(story, s, label):
    story.append(Paragraph(_esc(label), s["h2"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=ACCENT,
                            spaceBefore=1, spaceAfter=4))


def _bullets(items, s):
    return ListFlowable(
        [ListItem(Paragraph(_esc(it), s["body"]), leftIndent=10)
         for it in items if str(it).strip()],
        bulletType="bullet", bulletColor=ACCENT, start="•", leftIndent=12)


# Dimensions de la vignette photo (l'en-tête réserve exactement cette largeur).
_PHOTO_W = 32 * mm
_PHOTO_H = 40 * mm


def _photo_flowable(path, largeur=_PHOTO_W, hauteur=_PHOTO_H):
    """Image portrait (vignette) depuis `path`, ou None si absent/illisible.

    Renvoyer None permet de générer le CV sans photo sans planter.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        img = Image(path, width=largeur, height=hauteur, kind="proportional")
        img.hAlign = "RIGHT"
        return img
    except Exception:
        return None


def build_cv(profil, offre, sortie, with_photo=True):
    """Construit le PDF du CV à `sortie`. `offre` est un dict (titre, entreprise,
    lieu, url). `with_photo` : inclure la photo du profil si elle existe.
    Renvoie le chemin de sortie."""
    s = _styles()
    doc = SimpleDocTemplate(
        str(sortie), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"CV {profil.nom}", author=profil.nom)
    story = []

    # En-tête : bloc texte (nom, titre, coordonnées) à gauche, photo à droite
    # si le profil en fournit une valide. Sans photo -> en-tête simple.
    bloc_texte = [Paragraph(_esc(profil.nom), s["nom"])]
    if profil.titre:
        bloc_texte.append(Paragraph(_esc(profil.titre), s["titre"]))
    coords = " · ".join(x for x in (profil.ville, profil.telephone,
                                    profil.email) if x)
    if coords:
        bloc_texte.append(Paragraph(_esc(coords), s["coord"]))

    photo = _photo_flowable(getattr(profil, "photo", "")) if with_photo else None
    if photo is not None:
        # Deux colonnes : texte (large) | photo (largeur = celle de l'image,
        # collée à la marge droite pour s'aligner avec le bandeau en dessous).
        photo.hAlign = "RIGHT"
        entete = Table([[bloc_texte, photo]], colWidths=[None, _PHOTO_W])
        entete.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(entete)
    else:
        story.extend(bloc_texte)

    # Bandeau ciblé sur l'offre.
    cible = _ligne_cible(offre)
    if cible:
        story.append(Paragraph(cible, s["cible"]))

    # Résumé.
    if profil.resume:
        _section_title(story, s, "Profil")
        story.append(Paragraph(_esc(profil.resume), s["body"]))

    # Expériences.
    if profil.experiences:
        _section_title(story, s, "Expériences")
        for e in profil.experiences:
            titre = " — ".join(x for x in (e.poste, e.entreprise) if x)
            story.append(Paragraph(f"<b>{_esc(titre)}</b>", s["exp_titre"]))
            meta = " · ".join(x for x in (e.periode, e.lieu) if x)
            if meta:
                story.append(Paragraph(_esc(meta), s["exp_meta"]))
            if e.details:
                story.append(_bullets(e.details, s))

    # Formations.
    if profil.formations:
        _section_title(story, s, "Formations")
        for f in profil.formations:
            ligne = " — ".join(x for x in (f.intitule, f.etablissement) if x)
            if f.annee:
                ligne = f"{ligne} ({f.annee})" if ligne else f.annee
            story.append(Paragraph(_esc(ligne), s["body"]))

    # Compétences.
    if profil.competences:
        _section_title(story, s, "Compétences")
        story.append(Paragraph(_esc(" · ".join(profil.competences)), s["body"]))

    # Langues.
    if profil.langues:
        _section_title(story, s, "Langues")
        story.append(Paragraph(_esc(" · ".join(profil.langues)), s["body"]))

    doc.build(story)
    return str(sortie)


def _ligne_cible(offre):
    """Bandeau 'Candidature : {titre} — {entreprise} ({lieu})' + lien, ou ""."""
    titre = (offre or {}).get("titre", "")
    if not titre:
        return ""
    ent = offre.get("entreprise", "")
    lieu = offre.get("lieu", "")
    txt = f"Candidature : {_esc(titre)}"
    if ent:
        txt += f" — {_esc(ent)}"
    if lieu:
        txt += f" ({_esc(lieu)})"
    url = offre.get("url", "")
    if url:
        txt += f'<br/><font size="8">{_esc(url)}</font>'
    return txt
