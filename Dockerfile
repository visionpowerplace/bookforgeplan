# BookForge — manuscript-to-print-ready-book service
# The reason this lives in a container: WeasyPrint needs system Pango/Cairo
# libraries that are painful to install per-host. Here they're baked in once.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOOKFORGE_DATA=/data \
    PORT=8000

# WeasyPrint runtime libs + mime db (the libgdk-pixbuf/pango/cairo stack)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 libffi8 libcairo2 shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY bookforge_service/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# both packages: the engine and the service wrapper (fonts travel with the engine)
COPY bookforge/ ./bookforge/
COPY bookforge_service/ ./bookforge_service/

RUN mkdir -p /data
EXPOSE 8000

# single worker: the in-memory job store is per-process (see README to scale out)
CMD ["sh", "-c", "uvicorn bookforge_service.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]
