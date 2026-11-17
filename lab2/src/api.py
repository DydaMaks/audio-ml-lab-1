"""REST API для моделі AudioCNN із ЛР №1 (версія MLOps)."""
from __future__ import annotations
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from .model import AudioCNN, AudioPreprocessor, predict_bytes

MODEL_PATH = Path(os.getenv("MODEL_PATH", "artifacts/model.pt"))
MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_PATH.is_file():
        raise RuntimeError(f"Модель не знайдена: {MODEL_PATH}")
    torch.set_num_threads(2)
    cp = torch.load(MODEL_PATH, weights_only=True, map_location="cpu")
    net = AudioCNN()
    net.load_state_dict(cp["model_state"])
    net.eval()
    app.state.net = net
    app.state.prep = AudioPreprocessor().eval()
    info_path = MODEL_PATH.parent / "metrics.json"
    app.state.metrics = json.loads(info_path.read_text(encoding="utf-8"))
    yield

app = FastAPI(title="AudioCNN MLOps — Laboratory 2", version=MODEL_VERSION, lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True}

@app.get("/model-info")
def model_info():
    info = app.state.metrics
    return {
        "architecture": info["architecture"],
        "classes": ["yes", "no", "up", "down"],
        "model_size_kb": round(MODEL_PATH.stat().st_size / 1024, 2),
        "accuracy": info["accuracy_test_pct"],
        "accuracy_unit": "percent",
        "model_version": MODEL_VERSION,
        "test_count": info["split"]["test"],
    }

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Очікується .wav файл.")
    data = await file.read()
    start = time.perf_counter()
    try:
        result = predict_bytes(data, app.state.net, app.state.prep)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    latency = round((time.perf_counter() - start) * 1000, 3)
    return {
        "label": result["predicted_class"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "latency_ms": latency,
        "model_version": MODEL_VERSION,
    }
