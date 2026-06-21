# Image légère : pas de navigateur, juste httpx + pydantic.
FROM python:3.12-slim

WORKDIR /app

# Dépendances d'abord (cache des couches).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif.
COPY *.py ./

# Le conteneur fait un run unique puis s'arrête (adapté à un cron / timer).
# Le token Telegram est passé via l'environnement (-e ou --env-file).
ENTRYPOINT ["python", "scrape_24h.py"]
CMD ["--telegram"]
