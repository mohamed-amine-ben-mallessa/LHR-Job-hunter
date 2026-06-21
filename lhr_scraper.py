"""Scraping LHR — autonome, léger (httpx, sans navigateur).

Le détail des offres (JSON-LD JobPosting) est présent dans le HTML statique :
pas besoin de Chromium. Ne dépend que de `httpx` et de la lib standard, pour un
déploiement VPS léger. Si LHR change son HTML, ce sont ces regex qu'il faut
mettre à jour ; si LHR se met à bloquer les requêtes simples (anti-bot), voir le
plan B « Scrapling » documenté dans le README.
"""

import asyncio
import html as _html
import json
import re

import httpx

BASE_URL = "https://www.lhotellerie-restauration.fr"

# En-têtes d'un navigateur courant : LHR sert le HTML complet sans JS.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def build_list_url(region, metier, page=1):
    """URL de liste paginée pour une catégorie métier dans une région."""
    path = f"/emplois/{metier}/{region or 'france'}"
    url = BASE_URL + path
    if page > 1:
        url += f"?Page={page}"
    return url


# ── Cartes de la page liste ──────────────────────────────────────────────────

_CARD_RE = re.compile(
    r'<a[^>]*href="(/emploi/([0-9a-f]{8})/[^"]+/[^"]+)"[^>]*class="[^"]*job-item[^"]*"[^>]*>(.*?)</a>',
    re.S,
)
_TITLE_RE = re.compile(r'<h3[^>]*>(.*?)</h3>', re.S)
_LOC_RE = re.compile(r'<p[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</p>', re.S)
_EXCERPT_RE = re.compile(r'text-truncate--two-lines[^>]*>(.*?)</div>', re.S)


def _strip(s):
    return _html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def parse_list_cards(html_text):
    """Extrait les cartes d'offre d'une page de liste."""
    cards = []
    seen = set()
    for href, oid, body in _CARD_RE.findall(html_text):
        if oid in seen:
            continue
        seen.add(oid)
        title_m = _TITLE_RE.search(body)
        loc_m = _LOC_RE.search(body)
        exc_m = _EXCERPT_RE.search(body)
        cards.append({
            "id": oid,
            "url": BASE_URL + href,
            "titre": _strip(title_m.group(1)) if title_m else "",
            "lieu": _strip(loc_m.group(1)) if loc_m else "",
            "extrait": _strip(exc_m.group(1)) if exc_m else "",
        })
    return cards


# ── Détail d'une offre (JSON-LD) ─────────────────────────────────────────────

_LD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_HTML_DATE_RE = re.compile(r'job-offer-date[^>]*>(.*?)</', re.S)
_DATE_DDMMYYYY_RE = re.compile(r'\d{2}/\d{2}/\d{4}')
_DATE_ISO_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_DATETIME_ISO_RE = re.compile(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})')
_LOGO_IMG_RE = re.compile(r'<img[^>]*class="[^"]*logo-job[^"]*"[^>]*src="([^"]+)"')

_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
_EMAIL_SKIP = ("lhotellerie-restauration", "sentry", "example.", "@2x", ".png",
               ".jpg", ".jpeg", ".gif", ".webp", ".svg")
# Téléphone FR. Couvre :
#   - 06 81 77 46 26 / 06.81.77.46.26 / 06-81-77-46-26 / 0681774626 (collé)
#   - +33 6 81 77 46 26 / 0033 6 81 ... / +33681774626
#   - séparateurs mélangés, espaces insécables ( ), slash, point médian.
# On exige une frontière (pas un chiffre) avant/après pour éviter d'attraper un
# fragment au milieu d'un nombre plus long (prix, SIRET…).
_PHONE_SEP = r'[\s.  /·-]*'
_PHONE_RE = re.compile(
    r'(?<!\d)'
    r'(?:(?:\+33|0033)' + _PHONE_SEP + r'[1-9]|0[1-9])'
    r'(?:' + _PHONE_SEP + r'\d{2}){4}'
    r'(?!\d)')

# Email obfusqué LHR : chaque lettre dans un <span class=icon2X>.
_ICON2_SPAN_RE = re.compile(r'<span[^>]*class="?icon2([a-z]+)"?[^>]*>\s*</span>', re.I)
_ICON2_MAP = {"arobase": "@", "point": ".", "tiret": "-", "underscore": "_",
              "plus": "+"}


def _decode_icon2_email(html_fragment):
    """Reconstitue un email obfusqué LHR (suite de <span class=icon2X>), sinon ""."""
    chars = []
    for token in _ICON2_SPAN_RE.findall(html_fragment):
        chars.append(_ICON2_MAP.get(token, token if len(token) == 1 else ""))
    candidate = "".join(chars)
    m = _EMAIL_RE.search(candidate)
    return m.group(0) if m else ""


_BULLET_CHARS = "•▪●◦‣·–—►▶✓✔➤»"
_BULLET_LINE_RE = re.compile(
    r'(?m)^[ \t]*[' + re.escape(_BULLET_CHARS) + r'\?�][ \t]+')


def _clean_text(text):
    """Nettoie une description : retire spans d'obfuscation et HTML, décode les
    entités, normalise les puces et compacte les espaces."""
    if not text:
        return ""
    text = _ICON2_SPAN_RE.sub("", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = _BULLET_LINE_RE.sub("- ", text)
    text = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", text)
    return text.strip()


_EMPTY_DETAIL = {
    "entreprise": "", "salaire": "", "date_publication": "", "date_heure": "",
    "description": "", "code_postal": "", "pays": "", "email": "", "telephone": "",
}


def _not_spec(v):
    return "" if (v is None or str(v).strip() in ("", "Not Specified")) else str(v).strip()


def format_date(value):
    """Normalise une date en JJ/MM/AAAA (ISO du JSON-LD ou déjà JJ/MM/AAAA)."""
    s = (value or "").strip()
    if not s:
        return ""
    m = _DATE_ISO_RE.match(s)
    if m:
        y, mo, d = m.groups()
        return f"{d}/{mo}/{y}"
    m = _DATE_DDMMYYYY_RE.search(s)
    return m.group(0) if m else ""


def format_datetime(value):
    """Date + heure en 'JJ/MM/AAAA à HH:MM:SS' depuis l'ISO du JSON-LD."""
    s = (value or "").strip()
    if not s:
        return ""
    m = _DATETIME_ISO_RE.match(s)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        return f"{d}/{mo}/{y} à {hh}:{mm}:{ss}"
    return format_date(s)


def _html_date(html_text):
    """Date JJ/MM/AAAA visible dans la page (fallback du JSON-LD), sinon ""."""
    m = _HTML_DATE_RE.search(html_text)
    if not m:
        return ""
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    d = _DATE_DDMMYYYY_RE.search(text)
    return d.group(0) if d else ""


def _first_email(*texts):
    """Premier email plausible (best-effort), sinon ""."""
    for t in texts:
        for e in _EMAIL_RE.findall(t or ""):
            low = e.lower()
            if not any(s in low for s in _EMAIL_SKIP):
                return e
    return ""


def _normalize_phone(raw):
    """Normalise un numéro FR : +33/0033 -> 0, puis paires '06 40 30 11 29'."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0033"):
        digits = "0" + digits[4:]
    elif digits.startswith("33") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) != 10:
        return raw.strip()
    return " ".join(digits[i:i + 2] for i in range(0, 10, 2))


def _first_phone(*texts):
    """Premier numéro FR trouvé, normalisé, sinon ""."""
    for t in texts:
        m = _PHONE_RE.search(t or "")
        if m:
            return _normalize_phone(m.group(0))
    return ""


def parse_detail(html_text):
    """Extrait les champs détail depuis le JSON-LD JobPosting (filets inclus)."""
    for block in _LD_RE.findall(html_text):
        try:
            data = json.loads(_html.unescape(block.strip()), strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)
                         and d.get("@type") == "JobPosting"), {})
        if not isinstance(data, dict) or data.get("@type") != "JobPosting":
            continue
        out = dict(_EMPTY_DETAIL)
        org = data.get("hiringOrganization") or {}
        out["entreprise"] = _not_spec(org.get("name"))
        raw_desc = _not_spec(data.get("description"))
        obf_email = _decode_icon2_email(raw_desc) or _decode_icon2_email(html_text)
        out["description"] = _clean_text(raw_desc)
        date_posted = _not_spec(data.get("datePosted"))
        out["date_publication"] = format_date(date_posted)
        out["date_heure"] = format_datetime(date_posted)
        addr = ((data.get("jobLocation") or {}).get("address") or {})
        out["code_postal"] = _not_spec(addr.get("postalCode"))
        out["pays"] = _not_spec(addr.get("addressCountry"))
        sal = data.get("baseSalary") or {}
        val = (sal.get("value") or {})
        amount = _not_spec(val.get("value"))
        if amount:
            cur = _not_spec(sal.get("currency"))
            unit = _not_spec(val.get("unitText"))
            out["salaire"] = f"{amount} {cur}/{unit}".strip()
        if not out["date_publication"]:
            out["date_publication"] = _html_date(html_text)
        if not out["date_heure"]:
            out["date_heure"] = out["date_publication"]
        out["email"] = obf_email or _first_email(out["description"], html_text)
        out["telephone"] = _first_phone(out["description"])
        return out
    # Aucun JobPosting : on tente quand même date / email / tel.
    out = dict(_EMPTY_DETAIL)
    out["date_publication"] = _html_date(html_text)
    out["date_heure"] = out["date_publication"]
    out["email"] = _decode_icon2_email(html_text) or _first_email(html_text)
    out["telephone"] = _first_phone(_clean_text(html_text))
    return out


# ── Orchestration scrape ─────────────────────────────────────────────────────

_MAX_PAGES = 60


async def _fetch_html(client, url):
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.text or ""


async def scrape(region, metier, max_offres, delay=0.3, on_event=None):
    """Scrape la catégorie `metier` dans `region` jusqu'à `max_offres` offres.

    Récupère le détail complet de chaque offre (JSON-LD). `on_event`, si fourni,
    reçoit des messages de progression (str). Renvoie la liste des offres (dicts
    avec titre, lieu, entreprise, description, date_heure, email, telephone,
    code_postal, salaire, url).
    """
    def emit(msg):
        if on_event:
            on_event(msg)

    results = []
    seen = set()
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True,
                                 timeout=20.0) as client:
        page = 1
        while len(results) < max_offres and page <= _MAX_PAGES:
            url = build_list_url(region, metier, page)
            html_text = await _fetch_html(client, url)
            if delay:
                await asyncio.sleep(delay)
            new_cards = [c for c in parse_list_cards(html_text)
                         if c["id"] not in seen]
            emit(f"page {page}: {len(new_cards)} offres (total {len(results)})")
            if not new_cards:
                break
            for c in new_cards:
                seen.add(c["id"])
            page += 1
            for c in new_cards:
                try:
                    detail_html = await _fetch_html(client, c["url"])
                    if delay:
                        await asyncio.sleep(delay)
                    c.update(parse_detail(detail_html))
                except Exception:
                    pass
                results.append(c)
                if len(results) >= max_offres:
                    break
    return results[:max_offres]
