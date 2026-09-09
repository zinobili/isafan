# --- build the SPA -------------------------------------------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build          # -> /web/dist

# --- runtime -----------------------------------------------------------------
FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ISAFAN_HOST=0.0.0.0 \
    ISAFAN_PORT=8000 \
    ISAFAN_DATA_DIR=/data \
    ISAFAN_STATIC_DIR=/app/web/dist

WORKDIR /app

# ffmpeg comes bundled in the imageio-ffmpeg wheel — no apt package needed.
COPY server/requirements.txt server/requirements.txt
RUN pip install -r server/requirements.txt

COPY server/ server/
COPY --from=web /web/dist /app/web/dist

# Run unprivileged; /data is a mount point for the persistent volume.
RUN useradd --system --uid 10001 isafan \
    && mkdir -p /data && chown isafan /data
USER isafan
VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "-m", "server"]
