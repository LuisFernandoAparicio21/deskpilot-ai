# DeskPilot AI: image of the API in local mode (SQLite + Chroma), synthetic data only (T19, S17).
# Build:  docker build -t deskpilot-ai .
# Run:    docker run --rm -p 8000:8000 -e DESKPILOT_API_KEY=<at least 16 characters> deskpilot-ai
#
# Single stage on purpose: a multi-stage build would copy the site-packages and the data
# (~1 GB) a second time. Everything is prepared at build time, never inside a request
# (S7, RF-15): generate-data -> load-db -> index, plus the fastembed model downloaded once to
# data/vectordb/models (embeddings.cache_dir). The container needs no network at runtime.
# Build steps run as the non-root user, so no COPY --chown / chown -R layer duplicates files.
# No secret is baked in: .env is excluded by .dockerignore and the API key comes from the
# environment at `docker run`.
#
# Fabric mode (DESKPILOT_MODE=fabric) is NOT supported by this image: it needs the Microsoft
# ODBC Driver 18 for SQL Server (not installed here), whose licence must be accepted by
# whoever builds the image. pyodbc and unixODBC are present, the driver is not.

FROM python:3.13-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# unixODBC runtime: pyodbc imports libodbc even though local mode never opens a connection.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libodbc2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/data /app/logs \
    && chown app:app /app /app/data /app/logs

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY config.yaml main.py ./
COPY src ./src
COPY data/knowledge_base ./data/knowledge_base
COPY integrations/fabric/sql ./integrations/fabric/sql

USER app

# Seeded synthetic data, SQLite file and vector index (downloads the embedding model once).
RUN python main.py generate-data \
    && python main.py load-db \
    && python main.py index

ENV HF_HUB_OFFLINE=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import json,sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0 if json.load(r).get('status')=='ok' else 1)"]

# DESKPILOT_API_KEY is required (>= 16 characters) and is not part of the image.
CMD ["python", "main.py", "serve", "--host", "0.0.0.0"]
