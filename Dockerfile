# Nepantla: servidor FastAPI + la PWA, en una sola imagen.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEPANTLA_DATA_DIR=/data

# ffmpeg (con libopus) convierte las grabaciones del estudio a Opus.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY packs ./packs

# /data guarda la base SQLite, los audios y los respaldos diarios.
# En Railway hay que montar ahí un volumen (los volúmenes se montan como
# root, por eso esta imagen no cambia de usuario).
RUN mkdir -p /data
EXPOSE 8000

# --no-access-log: el servidor no escribe IP ni navegador de nadie.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log --no-server-header"]
