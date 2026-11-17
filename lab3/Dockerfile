# syntax=docker/dockerfile:1
FROM python:3.11-slim AS trainer
WORKDIR /build
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements-train.txt .
RUN pip install --no-cache-dir -r requirements-train.txt
COPY src/ ./src/
# Training is executed with docker run, not docker build.
ENV ARTIFACTS_DIR=/artifacts EPOCHS=6 MAX_PER_CLASS=500 MODEL_VERSION=1.0.0
ENTRYPOINT ["python", "-m", "src.train"]

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MODEL_PATH=/app/artifacts/model.pt MODEL_VERSION=1.0.0 PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src/ ./src/
COPY artifacts/model.pt ./artifacts/model.pt
COPY artifacts/labels.json ./artifacts/labels.json
COPY artifacts/metrics.json ./artifacts/metrics.json
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 CMD ["python", "-m", "src.healthcheck"]
CMD ["sh", "-c", "exec uvicorn src.api:app --host 0.0.0.0 --port ${PORT}"]
