"""Build metrics report from actual artifacts for Job Summary."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument("--metrics",default="metrics")
p.add_argument("--artifacts",default="artifacts")
p.add_argument("--out",default="metrics/report.md")
args=p.parse_args()
metric_dir=Path(args.metrics)
art_dir=Path(args.artifacts)
metric_dir.mkdir(parents=True,exist_ok=True)
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
info=load(art_dir/"metrics.json")
benchmark=load(metric_dir/"latency.json")
golden=load(metric_dir/"verify.json")
lines=["# Lab 3 — AudioCNN ML pipeline",
       f"- Trigger: `{os.getenv('GITHUB_EVENT_NAME','local')}`",
       f"- Commit: `{os.getenv('GITHUB_SHA','local')[:12]}`",
       f"- Epochs: **{info.get('epochs','n/a')}**",
       f"- Test accuracy: **{info.get('accuracy_test_pct','n/a')}%**",
       f"- Model size: **{info.get('model_size_kb','n/a')} KB**",
       f"- Golden samples: **{golden.get('passed','n/a')}/{golden.get('total','n/a')}**",
       f"- Latency server mean / p50 / p95: **{benchmark.get('server_ms',{}).get('mean','n/a')} / {benchmark.get('server_ms',{}).get('p50','n/a')} / {benchmark.get('server_ms',{}).get('p95','n/a')} ms**",
       f"- Latency client mean / p95: **{benchmark.get('client_ms',{}).get('mean','n/a')} / {benchmark.get('client_ms',{}).get('p95','n/a')} ms**",
       "", "Generated exclusively from current run artifacts."]
Path(args.out).write_text("\n".join(lines)+"\n",encoding="utf-8")
print("\n".join(lines))
