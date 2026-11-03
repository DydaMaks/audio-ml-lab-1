"""FastAPI: POST /predict для WAV і заміру latency_ms."""
from __future__ import annotations

from contextlib import asynccontextmanager
import time
from pathlib import Path

import torch
from fastapi import FastAPI, UploadFile, File, HTTPException

from model import AudioCNN, AudioPreprocessor, predict_bytes

MODEL = Path("saved_models/audio_cnn.pt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL.exists():
        raise RuntimeError("Модель відсутня: виконайте 'docker compose run --rm train'.")
    torch.set_num_threads(2)
    checkpoint = torch.load(MODEL, map_location="cpu", weights_only=True)
    model = AudioCNN()
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    app.state.model = model
    app.state.prep = AudioPreprocessor().eval()
    yield


app = FastAPI(title="Speech Commands / AudioCNN", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True}


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Потрібний .wav файл.")
    body = await file.read()
    start = time.perf_counter()
    try:
        result = predict_bytes(body, app.state.model, app.state.prep)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return result
