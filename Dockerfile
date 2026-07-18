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

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
