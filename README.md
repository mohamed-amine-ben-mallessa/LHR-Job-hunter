<div align="center">

<img src="assets/bot-logo.png" alt="LHR Job Hunter — scraper d'offres d'emploi hôtellerie-restauration vers Telegram" height="140" />

# 🍽️ LHR Job Hunter — Scraper d'offres d'emploi Hôtellerie-Restauration (Salle/Bar Île-de-France) vers Telegram

### Radar à jobs serveur · chef de rang · barman en Île-de-France — offres fraîches sur Telegram + génération de CV PDF, en Python léger (sans navigateur)

<sub>Données issues de <img src="assets/lhr-logo.png" alt="L'Hôtellerie Restauration" height="20" /> — projet indépendant, non affilié</sub>

**Scraper Python qui récupère les offres d'emploi _fraîches_ (≤ 24 h) de serveur, serveuse, chef de rang, barman/barmaid, runner et commis de salle en Île-de-France sur lhotellerie-restauration.fr, en extrait téléphone, email, salaire, contrat et horaires, puis te les envoie sur Telegram avec un CV PDF prêt à postuler.**

[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![No browser](https://img.shields.io/badge/scraping-httpx_(no_chromium)-success)](#-pourquoi-cest-léger)
[![Telegram](https://img.shields.io/badge/notifications-Telegram-26A5E4?logo=telegram&logoColor=white)](#-notifications-telegram)
[![Deploy: GitHub Actions](https://img.shields.io/badge/deploy-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](#-déploiement-en-1-minute)
[![Tests](https://img.shields.io/badge/tests-90_passing-brightgreen)](#-tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](#-contribuer)

<sub>⭐ <b>Si ça t'épargne d'ouvrir 40 annonces à la main, mets une étoile</b> — ça aide vraiment.</sub>

</div>

---

## 😩 Le problème

Les bons postes en salle partent en **quelques heures**. Quand tu vois l'annonce le lendemain, c'est déjà pourvu. Et même quand tu la vois à temps, il faut :

- ouvrir chaque offre une par une,
- chercher le **06/07** ou l'**email** noyés dans la description (souvent _masqués_ par le site),
- deviner s'il faut **postuler par mail** ou **se présenter avec un CV**.

## ✨ La solution

**LHR Job Hunter** scanne [lhotellerie-restauration.fr](https://www.lhotellerie-restauration.fr) **2× par jour**, garde uniquement les offres **publiées il y a moins de 24 h**, et t'envoie un message Telegram clé en main :

```
🍽️ Offres Salle/Bar Île-de-France (4 offres, <24h) — 21/06/2026

Chef de rang H/F — Quai Ouest
92 - Boulogne | 20/06/2026 à 08:33
📞 06 81 77 46 26 | 🧭 telephone
📄 CDI | ⏱️ 39h hebdo
💶 De 1900€ à 2200€ net mensuel
👤 Profil : Expérience en brasserie, maîtrise du port de plateau, anglais courant
→ Voir l'offre

Serveur H/F — Brasserie du Coin
75 - PARIS 5 | 20/06/2026 à 14:19
✉️ recrutement@exemple-resto.fr | 🧭 sur place
📄 CDD / Saisonnier
→ Voir l'offre
```

📎 Le **CSV complet est joint** au message (ouvrable dans Excel).

---

## 🚀 Fonctionnalités

| | |
|---|---|
| ⏱️ **Filtre 24 h** | Uniquement les offres fraîchement publiées — fini les annonces déjà pourvues. |
| 🎯 **Ciblage métier** | Serveur · serveuse · chef de rang · barman/barmaid · runner · commis de salle. Cuisine & encadrement exclus automatiquement. |
| 📞 **Téléphone & email** | Extraits, normalisés et **validés** — tous formats FR (`06`/`07`/`01`, avec ou sans espaces, `.`/`-`, `+33`…), y compris les emails _masqués_ par le site. |
| 🧭 **Mode de candidature** | Détecte `sur place` (déplacement avec CV), `email`, `téléphone` ou `non précisé`. Repère aussi les consignes **« ne pas se déplacer »** (⚠️) pour t'éviter un déplacement inutile. |
| 💶 **Salaire, contrat, horaires, profil** | Extraits depuis l'annonce : salaire en clair (`De 1700€ à 2100€ net`, `35,9K€`…), type de contrat (CDI/CDD/Extra…), volume horaire (`169H mensuel`, `39h hebdo`) et la section **Profil recherché**. |
| 📄 **CV PDF ciblé** | Génère un CV PDF pour une offre précise (en-tête « Candidature : … »), depuis ton profil. Sans IA, sans clé API (ReportLab). |
| 📨 **Telegram** | Accusé immédiat + résultat + CSV joint. Messages longs auto-découpés. |
| 🪶 **Ultra-léger** | `httpx` only — **pas de Chromium**. Tourne sur le plus petit VPS, ou gratuit sur GitHub Actions. |
| 🧪 **Fiable** | 90 tests unitaires. Validation Pydantic anti-faux-numéros / faux-emails. |

### 🧠 Les détails malins

Ce qui distingue ce scraper des autres :

- **Décodage des emails masqués** — le site obfusque les emails caractère par caractère dans des `<span>` ; le scraper les **reconstitue** pour récupérer le vrai contact.
- **Téléphone tous formats** — `06`, `07`, `01`, avec/sans espaces, `.`, `-`, `+33`, `0033`… normalisés en `06 81 77 46 26`, tout en **rejetant** les faux positifs (prix, SIRET).
- **« Ne pas se déplacer »** — détecte la *négation* : une annonce qui dit « candidature uniquement par mail » n'est jamais marquée « sur place », pour t'éviter un déplacement inutile.
- **Salaire en texte libre** — extrait `De 1700€ à 2100€ net`, `35,9K€`, `2 700 € net/mois`… même quand le JSON-LD ne le donne pas.
- **Anti-spam des données** — Pydantic valide chaque champ : un numéro qui n'est pas un vrai téléphone ou un `logo@2x.png` pris pour un email sont automatiquement écartés.
- **Robuste au site lent** — retry automatique sur les `504`/timeouts de la source, sans faire échouer tout le scan.

---

## 📈 Avancement du projet

Le cœur est **stable et utilisé en production** (scan quotidien automatique sur Telegram). Voici l'état des fonctionnalités :

| Statut | Fonctionnalité |
|:---:|---|
| ✅ | **Scraping** Salle/Bar Île-de-France (httpx, sans navigateur) |
| ✅ | **Filtre 24 h** + ciblage métier (serveur, chef de rang, barman, runner, commis) |
| ✅ | **Extraction** téléphone FR, email (même masqué), salaire, contrat, horaires, profil recherché |
| ✅ | **Détection du mode de candidature** (sur place / email / téléphone / via le site) |
| ✅ | **Validation Pydantic** (rejet des faux numéros / faux emails) |
| ✅ | **Notifications Telegram** (offres + CSV joint, messages auto-découpés) |
| ✅ | **Export CSV + JSON** (ouvrable dans Excel) |
| ✅ | **CV PDF ciblé** par offre (ReportLab, sans IA) — photo optionnelle |
| ✅ | **Déploiement** : GitHub Actions (gratuit), Docker, systemd |
| ✅ | **90 tests** unitaires, sans réseau |
| 🔜 | Autres régions / métiers (contributions bienvenues) |
| 🔜 | Sortie Slack / Discord / email en plus de Telegram |

> 💡 Tu veux une région ou un métier en plus ? Ouvre une *issue* ou une PR — l'architecture est pensée pour ça (voir [Contribuer](#-contribuer)).

---

## 🎯 Cas d'usage

- **🧑‍🍳 Extra / candidat** — sois le **premier** à appeler quand une annonce tombe. Le contact est déjà dans ton Telegram.
- **🏢 Agence d'intérim / placement** — un flux quotidien qualifié de postes de salle en IDF, exportable en CSV pour ton CRM.
- **📊 Veille marché RH** — suis le volume et les salaires des offres de service en temps quasi réel.
- **🤖 Brique d'automatisation** — branche le CSV/JSON sur n8n, un Google Sheet, ou ton propre pipeline.

---

## ⚡ Démarrage rapide

```bash
git clone https://github.com/mohamed-amine-ben-mallessa/LHR-Job-hunter.git
cd LHR-Job-hunter
pip install -r requirements.txt

# Génère offres_24h.csv + offres_24h.json
python scrape_24h.py

# …et envoie-les sur Telegram
python scrape_24h.py --telegram
```

> Pas de navigateur à installer, pas de clé API payante. Juste Python.

### Options

| Option | Défaut | Description |
|---|---|---|
| `--max N` | `120` | Nombre max d'offres parcourues. |
| `--heures H` | `24` | Fenêtre de fraîcheur (heures). |
| `--sortie PREFIXE` | `offres_24h` | Préfixe des fichiers de sortie. |
| `--telegram` | _off_ | Envoie sur le canal Telegram configuré. |

```bash
python scrape_24h.py --heures 48 --max 200      # fenêtre élargie
python scrape_24h.py --sortie offres_2026-06-21 # archivage daté
```

---

## 📨 Notifications Telegram

Avec `--telegram`, tu reçois **deux messages** : un accusé ⏳ immédiat (signe de vie même si le scan est lent), puis 🍽️ le résultat **avec le CSV joint**.

**Configuration** — copie `.env.example` en `.env` :

```env
TELEGRAM_BOT_TOKEN=123456789:AA...   # via @BotFather
TELEGRAM_CHAT_ID=@mon_canal          # ou un id -100… pour un canal privé
```

Le bot doit être **administrateur** du canal pour y poster.

---

## 📄 Générer un CV PDF pour une offre

Génère un CV PDF **ciblé sur une offre précise** du dernier scrape — sans IA, sans clé API. Le CV reprend ton profil et ajoute en tête un bandeau « Candidature : {titre} — {entreprise} » avec le lien de l'annonce.

```bash
# 1. Remplis ton profil une fois
cp profil.example.json profil.json
#   → édite profil.json (nom, expériences, compétences, langues…)

# 2. Scrape (génère offres_24h.json)
python scrape_24h.py

# 3. Génère le CV pour l'offre n°3 de la liste
python cv.py --offre 3
#   → cv_<entreprise>.pdf
```

Options :

| Option | Défaut | Description |
|---|---|---|
| `--offre N` | _(requis)_ | Index 1-based de l'offre dans le scrape. |
| `--metier M` | — | `rang`/`serveur` → `profil.json`, `barman` → `profil.barman.json`. |
| `--profil F` | `profil.json` | Fichier profil candidat (prioritaire sur `--metier`). |
| `--source F` | `offres_24h.json` | Fichier JSON du dernier scrape. |
| `--sortie F` | `cv_<entreprise>.pdf` | Chemin du PDF. |

Tu peux maintenir **plusieurs profils** (un par métier) et choisir au moment de générer :

```bash
python cv.py --offre 3                    # CV chef de rang (profil.json)
python cv.py --offre 3 --metier barman    # CV barman (profil.barman.json)
```

> Le PDF est produit par **ReportLab** (Python pur, aucune dépendance système). Ton `profil.json` reste local — il est ignoré par git (données personnelles).
>
> **Photo (optionnelle)** : ajoute `"photo": "assets/ta-photo.jpg"` dans ton profil pour l'afficher en haut à droite du CV (`build_cv(..., with_photo=False)` pour générer sans). **Email** : le champ `mail_template` (variables `{titre}`, `{entreprise}`, `{nom}`…) sert au brouillon d'email du bot Telegram.

### Envoyer le CV sur Telegram

Ajoute `--telegram` pour recevoir le PDF directement sur ton canal :

```bash
python cv.py --offre 3 --metier barman --telegram
```

### Depuis GitHub Actions (à distance, sans ton PC)

Le workflow [`cv.yml`](.github/workflows/cv.yml) se lance **à la demande** (onglet **Actions → Générer un CV → Run workflow**) : tu saisis le n° d'offre et le métier, le CV est généré et envoyé sur Telegram.

Comme `profil.json` est local (ignoré par git), fournis-le à GitHub via des secrets :

| Secret | Contenu |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | comme pour le scrape |
| `PROFIL_JSON` | colle tout le contenu de ton `profil.json` |
| `PROFIL_BARMAN_JSON` | _(optionnel)_ contenu de `profil.barman.json` |

> ⚠️ Mettre ton profil dans un secret GitHub stocke tes données perso chez GitHub (chiffrées). Si tu préfères les garder 100 % privées, génère le CV **en local** (`--telegram`) plutôt que via Actions.

---

## 🤖 Déploiement en 1 minute

### GitHub Actions — gratuit, zéro serveur _(recommandé)_

1. **Fork** ou clone ce repo sur ton compte.
2. **Settings → Secrets and variables → Actions** → ajoute `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`.
3. C'est tout. Le workflow [`daily.yml`](.github/workflows/daily.yml) tourne **2× par jour** (matin + soir) et tu peux le lancer à la main via l'onglet **Actions**.

> Le cron GitHub est en **UTC** (07:00 & 16:00 = 09:00/18:00 Paris l'été). Modifie les lignes `cron:` pour changer l'heure.

### Docker — pour héberger toi-même

```bash
docker compose run --rm scraper
```

Automatise via le cron de l'hôte :

```cron
0 9 * * *  cd /opt/LHR-Job-hunter && docker compose run --rm scraper
```

Image légère (~150 Mo, sans navigateur). Une alternative **systemd** (timer + `deploy.sh`) est fournie dans [`deploy/`](deploy/).

---

## 🪶 Pourquoi c'est léger

Beaucoup de scrapers embarquent un Chromium headless (~1,5 Go, 300-600 Mo de RAM). Ici, **le contenu des offres est dans le JSON-LD du HTML statique** : un simple `httpx.get` suffit.

| | Scraper navigateur | **LHR Job Hunter** |
|---|---|---|
| Image | ~1,5 Go | **~150 Mo** |
| RAM / run | 300-600 Mo | **~30-50 Mo** |
| Vitesse | ~2-3 s/offre | **~0,3 s/offre** |

---

## 🧪 Tests

```bash
python -m pytest -q          # 90 tests, sans réseau
```

Couvre : fenêtre 24 h, ciblage des intitulés, détection du mode de candidature (y compris « ne pas se déplacer »), extraction salaire/contrat/horaires/profil, formats de téléphone FR, validation Pydantic, formatage Telegram, génération du CV PDF.

---

## 🗂️ Structure

```
LHR-Job-hunter/
├── scrape_24h.py        # CLI scrape — point d'entrée
├── lhr_scraper.py       # scraping httpx (JSON-LD), autonome
├── extract.py           # filtres 24h / métier + détection candidature
├── models.py            # schémas Pydantic (validation)
├── telegram_notify.py   # envoi des offres + CSV sur Telegram
├── cv.py                # CLI génération CV PDF
├── cv_pdf.py            # rendu PDF (ReportLab)
├── cv_profile.py        # profil candidat (Pydantic)
├── profil.example.json  # gabarit de profil à copier en profil.json
├── .github/workflows/   # cron quotidien GitHub Actions
├── deploy/              # systemd (timer + deploy.sh)
├── Dockerfile · docker-compose.yml
└── tests/
```

---

## 🤝 Contribuer

PRs bienvenues — nouveaux métiers, autres régions, autres canaux (Slack, Discord, email)… Ouvre une *issue* pour discuter d'une idée.

---

## ⚠️ Disclaimer

> **Projet indépendant, non affilié** à L'Hôtellerie Restauration ni à aucun éditeur de site d'emploi. Le logo affiché est la propriété de **L'Hôtellerie Restauration** et n'est utilisé qu'à des fins d'identification de la source des données ; aucune affiliation ni approbation n'est sous-entendue.
>
> Cet outil interroge un site web public à des fins de **veille d'emploi personnelle**. En l'utilisant, **tu es seul responsable** :
> - du respect des **Conditions Générales d'Utilisation** du site cible (scraping, fréquence, robots.txt),
> - du respect du **RGPD** pour toute donnée de contact collectée (finalité, conservation limitée, information des personnes, pas de démarchage non sollicité),
> - de ne pas surcharger le site (l'outil temporise volontairement entre les requêtes).
>
> Fourni **« en l'état », sans garantie**. La structure du site peut changer à tout moment et casser l'extraction. À n'utiliser **que** dans le cadre d'une recherche d'emploi légitime.

---

## 📄 Licence

[MIT](LICENSE) — fais-en bon usage.

<div align="center"><sub>Si ce projet t'a aidé à décrocher un poste, ⭐ le repo et raconte-le en issue. 🍀</sub></div>
