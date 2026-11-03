"""Навчання AudioCNN; всі обчислення запускаються Docker-сервісом train."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import soundfile as sf
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

from model import AudioCNN, AudioPreprocessor, LABELS, SAMPLE_RATE
from prepare_data import ensure_data

ROOT = Path("data")
OUT = Path("saved_models")
METRICS = Path("metrics")
EPOCHS = 6
BATCH_SIZE = 32


def group_split(path: Path) -> str:
    # Всі записи одного мовця потрапляють в один і той самий split.
    speaker_id = path.stem.split("_nohash_")[0]
    bucket = int(hashlib.sha256((speaker_id + "_seed42").encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 80 else ("validation" if bucket < 90 else "test")


class CommandsDataset(Dataset):
    def __init__(self, split: str):
        self.items = [(wav, idx) for idx, label in enumerate(LABELS)
                      for wav in sorted((ROOT / label).glob("*.wav")) if group_split(wav) == split]
        self.prep = AudioPreprocessor()

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        path, label = self.items[index]
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        if sr != SAMPLE_RATE:
            raise RuntimeError(f"Неправильний sample rate: {path}")
        waveform = torch.from_numpy(data.mean(axis=1).copy())
        return self.prep(waveform), label


@torch.inference_mode()
def evaluate(net, loader):
    net.eval()
    good = 0
    total = 0
    for data, y in loader:
        predicted = net(data).argmax(1)
        good += int((predicted == y).sum())
        total += int(y.shape[0])
    return good / total if total else 0.0


def main():
    torch.manual_seed(42)
    random.seed(42)
    torch.set_num_threads(2)
    ensure_data()
    OUT.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)
    train = CommandsDataset("train")
    valid = CommandsDataset("validation")
    test = CommandsDataset("test")
    if min(len(train), len(valid), len(test)) == 0:
        raise RuntimeError("Один зі split порожній; перевірте вихідну вибірку.")
    print(f"Розподіл: train={len(train)}, validation={len(valid)}, test={len(test)}", flush=True)
    train_loader = DataLoader(train, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    valid_loader = DataLoader(valid, batch_size=BATCH_SIZE, num_workers=0)
    test_loader = DataLoader(test, batch_size=BATCH_SIZE, num_workers=0)
    net = AudioCNN()
    optimizer = torch.optim.Adam(net.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    best_val = -1.0
    history = []
    for epoch in range(1, EPOCHS + 1):
        net.train()
        running_loss = 0.0
        seen = 0
        for data, y in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = net(data)
            loss = loss_fn(logits, y)
            loss.backward()
            optimizer.step()
            running_loss += float(loss.item()) * len(y)
            seen += len(y)
        accuracy = evaluate(net, valid_loader)
        history.append({"epoch": epoch, "train_loss": round(running_loss / seen, 4), "val_accuracy": round(accuracy * 100, 2)})
        print(f"Епоха {epoch}/{EPOCHS}: loss={running_loss/seen:.4f}, val_accuracy={100*accuracy:.2f}%", flush=True)
        if accuracy > best_val:
            best_val = accuracy
            torch.save({"model_state": net.state_dict(), "labels": LABELS}, OUT / "audio_cnn.pt")
    checkpoint = torch.load(OUT / "audio_cnn.pt", map_location="cpu", weights_only=True)
    net.load_state_dict(checkpoint["model_state"])
    test_acc = evaluate(net, test_loader)
    weights = OUT / "audio_cnn.pt"
    metrics = {
        "dataset": "Google mini Speech Commands (4 класи)",
        "architecture": "AudioCNN: Conv2d(16)->Conv2d(32)->AdaptiveAvgPool2d(4x4)->Linear(64)->4",
        "num_parameters": sum(p.numel() for p in net.parameters()),
        "model_size_kb": round(weights.stat().st_size / 1024, 2),
        "split": {"train": len(train), "validation": len(valid), "test": len(test)},
        "epochs": EPOCHS,
        "accuracy_test_pct": round(100 * test_acc, 2),
        "best_validation_accuracy_pct": round(100 * best_val, 2),
        "history": history,
    }
    (METRICS / "training.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Фінальна тестова точність: {metrics['accuracy_test_pct']:.2f}%", flush=True)
    print(f"Розмір моделі: {metrics['model_size_kb']} КБ", flush=True)


if __name__ == "__main__":
    main()
