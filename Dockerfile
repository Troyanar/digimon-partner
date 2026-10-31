FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY static ./static

# Läuft nicht als root, mit eigener ID (rezepte hat 10001); Datenbank, 3D-Daten und App liegen im Volume /data
RUN useradd --system --uid 10020 --home-dir /app partner && mkdir -p /data && chown partner /data
USER partner

ENV HOST=0.0.0.0 PORT=8420 DATA_DIR=/data DEV=0
EXPOSE 8420
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/api/me', timeout=4)"
CMD ["python", "app.py"]
