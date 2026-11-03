"""Контейнерний тест REST API і середньої затримки 5 запитів."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

import requests
from model import LABELS
from train import group_split

SERVER = os.environ.get("API_URL", "http://api:8000")
METRICS = Path("metrics")


def main():
    METRICS.mkdir(exist_ok=True)
    status = requests.get(SERVER + "/health", timeout=30)
    status.raise_for_status()
    assert status.json()["status"] == "ok"
    results = []
    for label in LABELS:
        selected = [p for p in sorted((Path("data") / label).glob("*.wav")) if group_split(p) == "test"]
        if not selected:
            raise RuntimeError(f"Відсутні WAV для {label}")
        with selected[0].open("rb") as f:
            response = requests.post(SERVER + "/predict", files={"file": (selected[0].name, f, "audio/wav")}, timeout=30)
        response.raise_for_status()
        item = response.json()
        assert item["predicted_class"] in LABELS
        assert 0 <= item["confidence"] <= 1
        assert item["latency_ms"] >= 0
        results.append({"input_label": label, "file": selected[0].name, **item})
    # П'ятий тест повторює запит, щоб загалом було 5 вимірів.
    selected = [p for p in sorted((Path("data") / LABELS[0]).glob("*.wav")) if group_split(p) == "test"]
    with selected[1].open("rb") as f:
        response = requests.post(SERVER + "/predict", files={"file": (selected[1].name, f, "audio/wav")}, timeout=30)
    response.raise_for_status()
    results.append({"input_label": LABELS[0], "file": selected[1].name, **response.json()})
    avg = sum(r["latency_ms"] for r in results) / len(results)
    report = {"health": "passed", "requests": len(results), "mean_latency_ms": round(avg, 3), "results": results}
    (METRICS / "api_benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("/health: 200 OK")
    for r in results:
        print(f"{r['file']}: {r['predicted_class']} confidence={r['confidence']:.4f}, latency={r['latency_ms']:.3f} ms")
    print(f"Середня затримка API: {avg:.3f} мс")


if __name__ == "__main__":
    main()
