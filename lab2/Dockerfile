FROM python:3.11-slim AS trainer
ARG EPOCHS=6
ARG MAX_PER_CLASS=500
ARG MODEL_VERSION=1.0.0
ENV EPOCHS=${EPOCHS} MAX_PER_CLASS=${MAX_PER_CLASS} MODEL_VERSION=${MODEL_VERSION} PYTHONUNBUFFERED=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements-train.txt .
RUN pip install --no-cache-dir -r requirements-train.txt
COPY src/ ./src/
RUN python -m src.train

FROM python:3.11-slim AS runtime
ARG MODEL_VERSION=1.0.0
ARG GIT_COMMIT=unknown
LABEL org.opencontainers.image.title="audio-cnn-kws" \
      org.opencontainers.image.version="${MODEL_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src/ ./src/
COPY --from=trainer /build/artifacts ./artifacts
ENV MODEL_PATH=/app/artifacts/model.pt PORT=8000 MODEL_VERSION=${MODEL_VERSION} PYTHONUNBUFFERED=1
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 CMD ["python", "-m", "src.healthcheck"]
CMD ["sh", "-c", "exec uvicorn src.api:app --host 0.0.0.0 --port ${PORT}"]
