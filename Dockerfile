# AIC App Hosting clones the GitHub repo root. The real app is nested.
# ONE production image: RAC website (gunicorn :8080) + OCR worker (internal :8787).
ARG APP=shree-maruthi-travels-main/shree-maruthi-travels-main

FROM node:20-alpine AS rac-frontend
ARG APP
WORKDIR /ui
COPY ${APP}/rac/frontend/package.json ./
RUN npm install --legacy-peer-deps
COPY ${APP}/rac/frontend/ ./
ENV VITE_API_URL=/api/v1
RUN npm run build

FROM node:20-bookworm-slim AS wa-bridge
ARG APP
WORKDIR /wa
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY ${APP}/backend/wa_bridge/package.json ./
RUN npm install --omit=dev

FROM python:3.12-slim
ARG APP
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=wa-bridge /usr/local/bin/node /usr/local/bin/node
COPY ${APP}/backend/requirements.txt ./requirements.txt
COPY ${APP}/tools/wa_booking_ingest/requirements-worker.txt ./requirements-worker.txt
RUN pip install --no-cache-dir -r requirements.txt -r requirements-worker.txt

COPY ${APP}/backend/ ./backend/
COPY ${APP}/frontend/ ./frontend/
COPY ${APP}/tools/ ./tools/
COPY ${APP}/od_workspace/ ./od_workspace/
COPY ${APP}/start.sh ./start.sh
COPY --from=rac-frontend /ui/dist ./rac/frontend/dist
COPY --from=wa-bridge /wa/node_modules ./backend/wa_bridge/node_modules

RUN chmod +x ./start.sh

ENV PYTHONUNBUFFERED=1
ENV WHATSAPP_WATCHER_ENABLED=0
ENV OCR_PROVIDER=local
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV OCR_HTTP_PORT=8787
ENV DASHBOARD_HOST=0.0.0.0
ENV OCR_INGEST_URL=http://127.0.0.1:8787
ENV INGEST_REQUIRE_KEY=1

EXPOSE 8080

CMD ["sh", "./start.sh"]
