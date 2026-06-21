"""Envoi des offres sur un canal Telegram.

Le token du bot et l'identifiant du canal sont lus dans l'environnement
(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) — jamais dans le code. Découpe les
longs messages pour respecter la limite Telegram (~4096 caractères).
"""

import os

import httpx

API = "https://api.telegram.org"
_MAX_LEN = 3800  # marge sous la limite Telegram de 4096


class TelegramError(RuntimeError):
    pass


def _escape(text: str) -> str:
    """Échappe le HTML pour le parse_mode=HTML de Telegram."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_offre(o) -> str:
    """Formate une offre (objet Offre) en bloc HTML Telegram."""
    titre = _escape(o.titre)
    ent = _escape(o.entreprise) or "—"
    lieu = _escape(o.lieu)
    lignes = [f"<b>{titre}</b> — {ent}"]
    meta = " | ".join(x for x in (lieu, o.date_heure) if x)
    if meta:
        lignes.append(meta)
    contact = []
    if o.telephone:
        contact.append(f"📞 {o.telephone}")
    if o.email:
        contact.append(f"✉️ {_escape(o.email)}")
    contact.append(f"🧭 {o.candidature}")
    lignes.append(" | ".join(contact))
    if o.salaire:
        lignes.append(f"💶 {_escape(o.salaire)}")
    lignes.append(f'<a href="{_escape(o.url)}">Voir l\'offre</a>')
    return "\n".join(lignes)


def build_messages(offres, entete: str):
    """Construit la liste de messages (chunkés) à envoyer.

    Un message d'en-tête + les offres, regroupées tant qu'on tient sous la
    limite de longueur. Renvoie une liste de chaînes prêtes à poster.
    """
    blocs = [entete] + [format_offre(o) for o in offres]
    messages = []
    courant = ""
    for bloc in blocs:
        candidat = bloc if not courant else courant + "\n\n" + bloc
        if len(candidat) > _MAX_LEN and courant:
            messages.append(courant)
            courant = bloc
        else:
            courant = candidat
    if courant:
        messages.append(courant)
    return messages


def get_config():
    """Lit (token, chat_id) depuis l'environnement ; lève si absent."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise TelegramError(
            "TELEGRAM_BOT_TOKEN et/ou TELEGRAM_CHAT_ID manquants "
            "(définis-les dans l'environnement ou le fichier .env).")
    return token, chat_id


def send(messages, token=None, chat_id=None):
    """Envoie chaque message sur le canal. Renvoie le nombre envoyé."""
    if token is None or chat_id is None:
        token, chat_id = get_config()
    url = f"{API}/bot{token}/sendMessage"
    sent = 0
    with httpx.Client(timeout=20.0) as client:
        for msg in messages:
            resp = client.post(url, json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            if resp.status_code != 200:
                raise TelegramError(
                    f"Échec d'envoi Telegram ({resp.status_code}): {resp.text}")
            sent += 1
    return sent


def send_text(text, token=None, chat_id=None):
    """Envoie un unique message texte (ex. l'accusé « scraping en cours »)."""
    return send([text], token=token, chat_id=chat_id)


def send_document(path, caption="", token=None, chat_id=None):
    """Envoie un fichier (ex. le CSV) en pièce jointe sur le canal.

    Best-effort : si le fichier est absent, ne fait rien.
    """
    import os as _os

    if not path or not _os.path.exists(path):
        return False
    if token is None or chat_id is None:
        token, chat_id = get_config()
    url = f"{API}/bot{token}/sendDocument"
    with httpx.Client(timeout=60.0) as client:
        with open(path, "rb") as f:
            resp = client.post(
                url,
                data={"chat_id": chat_id, "caption": caption[:1000]},
                files={"document": (_os.path.basename(path), f, "text/csv")},
            )
    if resp.status_code != 200:
        raise TelegramError(
            f"Échec d'envoi du document ({resp.status_code}): {resp.text}")
    return True
