"""Мінімальні unit-перевірки для базового рівня (реальний запуск у Docker)."""
import io
import math
import wave

import pytest
import torch

from model import AudioCNN, AudioPreprocessor, LABELS, SAMPLE_RATE, decode_wav, predict_bytes


def create_wav(hz=440.0, seconds=0.25):
    import struct
    n = int(SAMPLE_RATE * seconds)
    frames = b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * hz * i / SAMPLE_RATE))) for i in range(n))
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(frames)
    return buf.getvalue()


def test_wav_and_mel_shape():
    sample = decode_wav(create_wav())
    transformed = AudioPreprocessor()(sample)
    assert transformed.shape[0] == 1
    assert transformed.shape[1] == 64
    assert torch.isfinite(transformed).all()


def test_predict_json_schema():
    model = AudioCNN().eval()
    result = predict_bytes(create_wav(), model, AudioPreprocessor().eval())
    assert result['predicted_class'] in LABELS
    assert 0 <= result['confidence'] <= 1
    assert set(result['probabilities']) == set(LABELS)


def test_reject_invalid_audio():
    with pytest.raises(ValueError, match='WAV'):
        decode_wav(b'not-a-wav')
