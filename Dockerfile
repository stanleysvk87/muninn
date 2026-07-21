# Stage 1: build the frontend -------------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: python runtime -------------------------------------------------
FROM python:3.11-slim
WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /src/frontend/dist /app/frontend/dist

# Single process serves both the API and the built frontend (SPA fallback +
# GZip + cache headers in app/main.py) — no nginx/Caddy needed, see
# docs/adr/0002-single-process-no-reverse-proxy.md.
ENV MUNINN_DATA_DIR=/app/data \
    MUNINN_ARCHIVE_DIR=/app/archive \
    MUNINN_DB_PATH=/app/data/muninn.db \
    MUNINN_FRONTEND_DIST_DIR=/app/frontend/dist

# Must NOT run as root: the claude CLI refuses --dangerously-skip-permissions
# (which our claude_cli provider relies on for headless extraction) when
# invoked as root/sudo, as a hard-coded safety guard. UID 1000 matches the
# typical single-user homelab host account so bind-mounted volumes (data,
# archive, ~/.claude) need no extra chown gymnastics.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin muninn \
    && mkdir -p /app/data /app/archive \
    && chown -R muninn:muninn /app
USER muninn

EXPOSE 8000

# No curl/wget in this slim image -- python is already here. 127.0.0.1, not
# localhost: uvicorn only binds IPv4 (--host 0.0.0.0), and localhost
# resolves to ::1 first in these containers -- confirmed on Sindri (same
# base image family) that clients which don't retry the next resolved
# address report a false unhealthy against a perfectly fine service.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
