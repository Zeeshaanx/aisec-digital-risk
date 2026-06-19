# ─────────────────────────────────────────────────────────────
# Single-container build: PostgreSQL + Redis + SearXNG + FastAPI + Nginx
# Usage:
#   docker build -t aisec-digital-risk .
#   docker run -d -p 8080:80 --env-file .env aisec-digital-risk
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="aisec-team"

# ── System packages ──
RUN apt-get update && apt-get install -y --no-install-recommends \
        # PostgreSQL
        postgresql postgresql-client \
        # Redis
        redis-server \
        # Nginx
        nginx \
        # Supervisord
        supervisor \
        # Build tools for Python deps
        build-essential libpq-dev \
        # Utilities
        curl wget gosu git \
        # SearXNG runtime deps
        python3-babel python3-flask \
    && rm -rf /var/lib/apt/lists/*

# ── Install SearXNG ──
RUN pip install --no-cache-dir searxng==2024.11.4.post0 || \
    pip install --no-cache-dir searx==1.0.0 || \
    (git clone https://github.com/searxng/searxng /opt/searxng && \
     pip install --no-cache-dir -r /opt/searxng/requirements.txt)

# ── Install Python dependencies for FastAPI ──
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ──
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY app/ ./app/
COPY run.py .

# ── Copy SearXNG settings ──
RUN mkdir -p /etc/searxng
COPY searxng/settings.yml /etc/searxng/settings.yml

# ── Copy Nginx config ──
COPY nginx/nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# ── Copy supervisord config ──
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# ── Copy startup scripts ──
COPY scripts/init-postgres.sh /scripts/init-postgres.sh
COPY scripts/start-searxng.sh /scripts/start-searxng.sh
COPY scripts/start-fastapi.sh /scripts/start-fastapi.sh
RUN chmod +x /scripts/*.sh

# ── PostgreSQL setup ──
RUN mkdir -p /var/run/postgresql && \
    chown postgres:postgres /var/run/postgresql && \
    mkdir -p /var/lib/postgresql/data && \
    chown postgres:postgres /var/lib/postgresql/data

# ── Nginx setup ──
RUN mkdir -p /var/log/nginx /var/lib/nginx/body && \
    chown -R www-data:www-data /var/log/nginx

# ── Supervisor log dir ──
RUN mkdir -p /var/log/supervisor

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost/aisec-digital-risk/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
