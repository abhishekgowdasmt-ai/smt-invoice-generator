FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY tools/ ./tools/

# Expose port
EXPOSE 8080

# Start gunicorn (production WSGI server)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "2", "--timeout", "120", "backend.app:app"]
