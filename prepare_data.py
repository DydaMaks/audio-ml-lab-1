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


def is_real_wav(name: str) -> bool:
    """Пропустити AppleDouble/службові файли macOS та залишити аудіо WAV."""
    parts = PurePosixPath(name).parts
    return (
        bool(parts)
        and name.lower().endswith(".wav")
        and not any(part == "__MACOSX" or part.startswith(".") for part in parts)
    )


def ensure_data() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    completed = ROOT / ".speech_commands_ready"
    if completed.exists() and all(
        len([p for p in (ROOT / c).glob("*.wav") if is_real_wav(p.name)]) >= SAMPLES_PER_CLASS
        for c in LABELS
    ):
        print("[data] Вибірку вже підготовлено.", flush=True)
        return

    if not ZIP_PATH.exists():
        print("[data] Завантаження Google mini Speech Commands (~182 МБ)...", flush=True)
        urllib.request.urlretrieve(URL, ZIP_PATH)

    try:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            members = {c: [] for c in LABELS}
            for m in archive.infolist():
                if m.is_dir() or not is_real_wav(m.filename):
                    continue
                parts = PurePosixPath(m.filename).parts
                for c in LABELS:
                    if c in parts[:-1]:
                        members[c].append(m)
                        break

            for label in LABELS:
                entries = members[label]
                if len(entries) < SAMPLES_PER_CLASS:
                    raise RuntimeError(f"Для {label} знайдено лише {len(entries)} реальних WAV.")
                rng = random.Random(42)
                rng.shuffle(entries)
                dest = ROOT / label
                dest.mkdir(exist_ok=True)

                # Видалити службові WAV-файли, якщо вони залишилися від попереднього запуску.
                for existing in dest.glob("*.wav"):
                    if not is_real_wav(existing.name):
                        existing.unlink()

                for m in entries[:SAMPLES_PER_CLASS]:
                    file_name = PurePosixPath(m.filename).name
                    (dest / file_name).write_bytes(archive.read(m))
                print(f"[data] {label}: {SAMPLES_PER_CLASS} WAV", flush=True)

        completed.write_text("ok", encoding="utf-8")
    finally:
        if completed.exists():
            ZIP_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    ensure_data()
