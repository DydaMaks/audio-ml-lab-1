"""Базова модель AudioCNN та підготовка WAV для розпізнавання команд."""
from __future__ import annotations

import io
import torch
import torchaudio
import soundfile as sf
from torch import nn
import torch.nn.functional as F

LABELS = ("yes", "no", "up", "down")
SAMPLE_RATE = 16_000
SAMPLES = SAMPLE_RATE


class AudioCNN(nn.Module):
    def __init__(self, num_classes: int = 4):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 4 * 4, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


class AudioPreprocessor(nn.Module):
    def __init__(self):
        super().__init__()
        self.mel = torchaudio.transforms.MelSpectrogram(
            sample_rate=SAMPLE_RATE, n_fft=400, win_length=400, hop_length=160,
            n_mels=64, f_min=50.0, f_max=8000.0, power=2.0,
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        # Для одного запису форма [16000] -> [1, 64, 101].
        if waveform.ndim != 1:
            raise ValueError("Очікується одноканальний аудіосигнал.")
        if waveform.numel() > SAMPLES:
            waveform = waveform[:SAMPLES]
        elif waveform.numel() < SAMPLES:
            waveform = F.pad(waveform, (0, SAMPLES - waveform.numel()))
        mel = self.mel(waveform)
        return torch.log1p(mel).unsqueeze(0)


def decode_wav(content: bytes) -> torch.Tensor:
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("WAV перевищує обмеження 5 МБ.")
    try:
        wave, sr = sf.read(io.BytesIO(content), dtype="float32", always_2d=True)
    except Exception as exc:
        raise ValueError("Неможливо прочитати WAV-файл.") from exc
    if wave.shape[0] == 0:
        raise ValueError("Порожній аудіозапис.")
    if wave.shape[0] / sr > 10.0:
        raise ValueError("Тривалість запису перевищує 10 секунд.")
    wave = torch.from_numpy(wave.mean(axis=1).copy())
    if sr != SAMPLE_RATE:
        wave = torchaudio.functional.resample(wave, sr, SAMPLE_RATE)
    return wave


@torch.inference_mode()
def predict_bytes(content: bytes, model: AudioCNN, prep: AudioPreprocessor):
    wav = decode_wav(content)
    logits = model(prep(wav).unsqueeze(0))
    probabilities = torch.softmax(logits, dim=1)[0]
    index = int(torch.argmax(probabilities))
    return {
        "predicted_class": LABELS[index],
        "confidence": round(float(probabilities[index]), 4),
        "probabilities": {name: round(float(probabilities[i]), 4) for i, name in enumerate(LABELS)},
    }
