FROM node:20-alpine AS rac-frontend
WORKDIR /ui
COPY rac/frontend/package.json ./
RUN npm install --legacy-peer-deps
COPY rac/frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY tools/ ./tools/
COPY --from=rac-frontend /ui/dist ./rac/frontend/dist

EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 backend.app:app"]
