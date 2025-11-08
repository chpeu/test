# Dockerfile pour Trade Cursor v7.0
# Permet de conteneuriser l'application pour faciliter le déploiement multi-instances

FROM python:3.11-slim

# Métadonnées
LABEL maintainer="Trade Cursor Bot"
LABEL description="Automated trading bot for MEXC Futures with scalability scanning"
LABEL version="7.0"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Argument pour le port (peut être surchargé au build)
ARG PORT=5000
ENV PORT=${PORT}

# Créer répertoire de travail
WORKDIR /app

# Copier requirements et installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Créer répertoires pour les données persistantes
RUN mkdir -p data logs

# Exposer le port (variable selon l'instance)
EXPOSE ${PORT}

# Healthcheck pour vérifier que l'app est alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT}/api/config', timeout=5)" || exit 1

# Script de démarrage
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --log-level info
