"""Перевірка accuracy на тестових WAV, спакованих під час навчання."""
import argparse
import json
from pathlib import Path
import soundfile as sf
import torch
from .model import AudioCNN, AudioPreprocessor, LABELS

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifacts", default="artifacts")
    args=p.parse_args()
    root=Path(args.artifacts)
    cp=torch.load(root / "model.pt", map_location="cpu", weights_only=True)
    net=AudioCNN()
    net.load_state_dict(cp["model_state"])
    net.eval()
    prep=AudioPreprocessor().eval()
    correct=total=0
    torch.set_num_threads(2)
    with torch.inference_mode():
        for idx,label in enumerate(LABELS):
            for wav in sorted((root/"testset"/label).glob("*.wav")):
                audio,sr=sf.read(str(wav), dtype="float32", always_2d=True)
                if sr!=16000: raise RuntimeError("Bad WAV sample rate")
                inp=prep(torch.from_numpy(audio.mean(axis=1).copy())).unsqueeze(0)
                pred=int(net(inp).argmax(1).item())
                correct+=pred==idx
                total+=1
    if total==0: raise RuntimeError("Тестова вибірка порожня")
    outcome={"count":total,"correct":correct,"accuracy_pct":round(100*correct/total,2)}
    print(json.dumps(outcome,ensure_ascii=False),flush=True)
    return outcome

if __name__=="__main__": main()
