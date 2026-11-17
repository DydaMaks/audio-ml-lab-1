"""Однаковий benchmark для local venv та Docker: 10 warmup + 100 POST."""
from __future__ import annotations
import argparse
import json
import statistics
import time
from pathlib import Path
import requests

def percentile(values: list[float], percent: float) -> float:
    items=sorted(values)
    pos=(len(items)-1)*percent/100
    left=int(pos)
    right=min(len(items)-1,left+1)
    return items[left]+(items[right]-items[left])*(pos-left)

def aggregate(values: list[float]) -> dict:
    return {
        "mean": round(statistics.fmean(values),3),
        "p50": round(percentile(values,50),3),
        "p95": round(percentile(values,95),3),
        "n": len(values),
    }

def run(url: str, wav: Path, requests_n: int = 100, warmups: int = 10) -> dict:
    if not wav.is_file():
        raise FileNotFoundError(wav)
    data=wav.read_bytes()
    session=requests.Session()
    server_ms=[]
    client_ms=[]
    for i in range(warmups+requests_n):
        start=time.perf_counter()
        response=session.post(
            url.rstrip("/")+"/predict",
            files={"file":("yes.wav",data,"audio/wav")},
            timeout=30,
        )
        end=time.perf_counter()
        response.raise_for_status()
        payload=response.json()
        assert payload["label"] in ("yes","no","up","down")
        assert 0 <= payload["confidence"] <= 1
        assert payload["latency_ms"] >= 0
        if i>=warmups:
            server_ms.append(float(payload["latency_ms"]))
            client_ms.append((end-start)*1000)
    session.close()
    return {
        "warmups":warmups,
        "requests":requests_n,
        "server_ms":aggregate(server_ms),
        "client_ms":aggregate(client_ms),
        "wav":wav.name,
    }

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--url",default="http://127.0.0.1:8000")
    arg.add_argument("--wav",default="artifacts/samples/yes.wav")
    arg.add_argument("--n",type=int,default=100)
    arg.add_argument("--warmups",type=int,default=10)
    arg.add_argument("--out",default="")
    args=arg.parse_args()
    results=run(args.url,Path(args.wav),args.n,args.warmups)
    output=json.dumps(results,ensure_ascii=False,indent=2)
    print(output)
    if args.out: Path(args.out).write_text(output,encoding="utf-8")
