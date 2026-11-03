"""Завантаження відкритої підмножини Google Speech Commands усередині Docker."""
from __future__ import annotations

import random
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from model import LABELS

URL = "https://storage.googleapis.com/download.tensorflow.org/data/mini_speech_commands.zip"
ROOT = Path("data")
ZIP_PATH = ROOT / "mini_speech_commands.zip"
SAMPLES_PER_CLASS = 500


def ensure_data() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    completed = ROOT / ".speech_commands_ready"
    if completed.exists() and all(len(list((ROOT / c).glob("*.wav"))) >= SAMPLES_PER_CLASS for c in LABELS):
        print("[data] Вибірку вже підготовлено.", flush=True)
        return
    if not ZIP_PATH.exists():
        print("[data] Завантаження Google mini Speech Commands (~182 МБ)...", flush=True)
        urllib.request.urlretrieve(URL, ZIP_PATH)
    try:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            members = {c: [] for c in LABELS}
            for m in archive.infolist():
                parts = PurePosixPath(m.filename).parts
                if m.is_dir() or not m.filename.lower().endswith(".wav"):
                    continue
                for c in LABELS:
                    if c in parts[:-1]:
                        members[c].append(m)
                        break
            for label in LABELS:
                entries = members[label]
                if len(entries) < SAMPLES_PER_CLASS:
                    raise RuntimeError(f"Для {label} знайдено лише {len(entries)} аудіо.")
                rng = random.Random(42)
                rng.shuffle(entries)
                dest = ROOT / label
                dest.mkdir(exist_ok=True)
                for m in entries[:SAMPLES_PER_CLASS]:
                    file_name = PurePosixPath(m.filename).name
                    (dest / file_name).write_bytes(archive.read(m))
                print(f"[data] {label}: {SAMPLES_PER_CLASS} WAV", flush=True)
        completed.write_text("ok", encoding="utf-8")
    finally:
        # Зменшує зайняте місце після розпакування потрібних класів.
        if completed.exists():
            ZIP_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    ensure_data()
