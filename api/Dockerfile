# Image de l'API. Contexte de construction : racine du dépôt (moteur, données et règles métier en dépendent).
#   docker build -f api/Dockerfile -t commission-api .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data \
    KNOWLEDGE_PATH=/app/knowledge/regles-metier.md \
    PORT=8000

WORKDIR /app

COPY engine/pyproject.toml engine/pyproject.toml
COPY engine/commission_engine engine/commission_engine
COPY api/pyproject.toml api/pyproject.toml
COPY api/commission_api api/commission_api
RUN pip install ./engine ./api

COPY data data
COPY knowledge knowledge

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')"

# --proxy-headers : derrière l'hébergeur, l'adresse du visiteur (limitation de débit) vient de X-Forwarded-For.
CMD ["sh", "-c", "exec uvicorn commission_api.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
