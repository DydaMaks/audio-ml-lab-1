"""Golden-sample check against live FastAPI. Exits nonzero for any mismatch."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import requests

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:8000")
    parser.add_argument("--expected",default="artifacts/samples/expected.json")
    parser.add_argument("--out",default="metrics/verify.json")
    args=parser.parse_args()
    source=Path(args.expected)
    expected=json.loads(source.read_text(encoding="utf-8"))
    results=[]
    for name,truth in sorted(expected.items()):
        wav=source.parent/name
        response=requests.post(args.url.rstrip("/")+"/predict", files={"file":(name,wav.read_bytes(),"audio/wav")},timeout=30)
        response.raise_for_status()
        found=response.json()["label"]
        results.append({"wav":name,"expected":truth,"predicted":found,"passed":found==truth})
    output={"passed":sum(row["passed"] for row in results),"total":len(results),"details":results}
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))
    if not results or output["passed"]!=output["total"]:
        raise SystemExit(1)

if __name__=="__main__": main()
