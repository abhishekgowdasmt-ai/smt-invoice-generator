FROM node:20-alpine AS rac-frontend
WORKDIR /ui
COPY rac/frontend/package.json ./
RUN npm install --legacy-peer-deps
COPY rac/frontend/ ./
RUN npm run build

FROM node:20-bookworm-slim AS wa-bridge
WORKDIR /wa
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY backend/wa_bridge/package.json ./
RUN npm install --omit=dev

FROM python:3.12-slim
WORKDIR /app

COPY --from=wa-bridge /usr/local/bin/node /usr/local/bin/node
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY tools/ ./tools/
COPY start.sh ./start.sh
COPY --from=rac-frontend /ui/dist ./rac/frontend/dist
COPY --from=wa-bridge /wa/node_modules ./backend/wa_bridge/node_modules

RUN chmod +x ./start.sh

EXPOSE 8080

CMD ["sh", "./start.sh"]
