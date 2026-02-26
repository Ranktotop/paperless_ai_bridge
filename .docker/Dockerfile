# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

ARG VERSION=dev
ENV APP_VERSION=${VERSION} \
    ROOT_DIR=/app

LABEL description="Paperless AI Bridge — FastAPI middleware for Paperless-ngx" \
      version="${VERSION}"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the source trees needed at runtime
COPY server/   ./server/
COPY shared/   ./shared/
COPY sync/     ./sync/
COPY config/   ./config/
COPY start.sh  ./start.sh

# API port
EXPOSE 8080

# Run as non-root for security
RUN useradd --no-create-home --shell /bin/false aibridge && \
    chmod +x start.sh && \
    mkdir -p /app/logs && \
    chown aibridge /app/logs
USER aibridge

CMD ["./start.sh"]
