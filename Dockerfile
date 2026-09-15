# AIC App Hosting clones the GitHub repo root. The real app is nested.
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

COPY --from=wa-bridge /usr/local/bin/node /usr/local/bin/node
COPY ${APP}/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ${APP}/backend/ ./backend/
COPY ${APP}/frontend/ ./frontend/
COPY ${APP}/tools/ ./tools/
COPY ${APP}/od_workspace/ ./od_workspace/
COPY ${APP}/start.sh ./start.sh
COPY --from=rac-frontend /ui/dist ./rac/frontend/dist
COPY --from=wa-bridge /wa/node_modules ./backend/wa_bridge/node_modules

RUN chmod +x ./start.sh

EXPOSE 8080

CMD ["sh", "./start.sh"]
