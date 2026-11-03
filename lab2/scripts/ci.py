#!/usr/bin/env python3
"""Доказові MLOps-вимірювання на одному GitHub-host: venv/single/multi."""
from __future__ import annotations
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
import requests
from benchmark import run as benchmark_run

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"results"
LOGS=RESULTS/"logs"
RESULTS.mkdir(parents=True,exist_ok=True)
LOGS.mkdir(parents=True,exist_ok=True)
os.chdir(ROOT)

def run(command, logfile=None, check=True, env=None, cwd=ROOT):
    print("$ "+" ".join(str(x) for x in command),flush=True)
    completed=subprocess.run([str(x) for x in command],cwd=cwd,env=env,
                             text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    stdout=completed.stdout or ""
    if logfile:
        (LOGS/logfile).write_text("$ "+" ".join(map(str,command))+"\n"+stdout,encoding="utf-8")
    if stdout: print(stdout[-9000:],flush=True)
    if check and completed.returncode:
        raise RuntimeError(f"Команда завершилася з кодом {completed.returncode}: {command}\n{stdout[-2400:]}")
    return stdout

def first_successful_health(timeout=60):
    end=time.monotonic()+timeout
    last=""
    while time.monotonic()<end:
        try:
            response=requests.get("http://127.0.0.1:8000/health",timeout=1)
            if response.status_code==200 and response.json().get("status")=="ok":
                return response.json()
            last=f"HTTP {response.status_code}"
        except Exception as e:
            last=str(e)
        time.sleep(0.12)
    raise RuntimeError("API /health не став доступним: "+last)

def wait_docker_healthy(name,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        state=run(["docker","inspect","--format","{{.State.Health.Status}}",name],check=False).strip()
        if state=="healthy": return
        if state=="unhealthy": raise RuntimeError("HEALTHCHECK unhealthy: "+name)
        time.sleep(1.0)
    raise RuntimeError("Контейнер не отримав статус healthy: "+name)

def smoke(prefix):
    health=requests.get("http://127.0.0.1:8000/health",timeout=10)
    info=requests.get("http://127.0.0.1:8000/model-info",timeout=10)
    swagger=requests.get("http://127.0.0.1:8000/docs",timeout=10)
    bad=requests.post("http://127.0.0.1:8000/predict",
                      files={"file":("bad.wav",b"not an audio file","audio/wav")},timeout=10)
    wav=(ROOT/"artifacts/samples/yes.wav").read_bytes()
    good=requests.post("http://127.0.0.1:8000/predict",
                       files={"file":("yes.wav",wav,"audio/wav")},timeout=10)
    assert health.status_code==info.status_code==swagger.status_code==good.status_code==200
    assert bad.status_code==400
    payload=info.json()
    assert payload["accuracy"]>0 and payload["model_size_kb"]>0
    assert good.json()["model_version"]=="1.0.0"
    msg=(f"=== {prefix} ===\nGET /health: HTTP {health.status_code} {health.text}\n"
         f"GET /model-info: HTTP {info.status_code} {info.text}\n"
         f"GET /docs: HTTP {swagger.status_code}\n"
         f"POST /predict valid: HTTP {good.status_code} {good.text}\n"
         f"POST /predict bad WAV: HTTP {bad.status_code} {bad.text}\n")
    (LOGS/("smoke-"+prefix+".log")).write_text(msg,encoding="utf-8")
    print(msg,flush=True)
    return payload

def local_rss_mb(pid):
    output=run(["ps","-o","rss=","-p",str(pid)],check=False)
    try: return round(int(output.strip().splitlines()[-1])/1024,2)
    except Exception: return None

def bytes_to_mb(x):
    value=float(x)
    return round(value/(1024*1024),2)

def docker_mem_mb(name):
    line=run(["docker","stats","--no-stream","--format","{{.MemUsage}}",name])
    (LOGS/("stats-"+name+".log")).write_text("docker stats --no-stream "+name+"\n"+line,encoding="utf-8")
    m=re.search(r"([\d.]+)\s*([KMG]i?B)",line,re.I)
    if not m: return None
    val=float(m.group(1))
    unit=m.group(2).lower()
    return round(val*({"kib":1/1024,"mib":1,"gib":1024,"kb":1/1000,"mb":1,"gb":1000}[unit]),2)

def local_evaluation(python):
    output=run([python,"-m","src.evaluate"],"evaluate-local.log")
    return json.loads(output.strip().splitlines()[-1])

def docker_evaluation(name):
    output=run(["docker","exec",name,"python","-m","src.evaluate"],"evaluate-"+name+".log")
    return json.loads(output.strip().splitlines()[-1])

def image_bytes(tag):
    return int(run(["docker","image","inspect",tag,"--format","{{.Size}}"]).strip().splitlines()[-1])

def hash_model(tag,path):
    return run(["docker","run","--rm","--entrypoint","sha256sum",tag,path]).strip().split()[0]

def measure_local():
    venv=ROOT/".venv"
    if not venv.is_dir():
        run([sys.executable,"-m","venv",venv],"venv-create.log")
    python=str(venv/"bin/python")
    run([python,"-m","pip","install","--no-cache-dir","-r","requirements-api.txt"],"venv-pip.log")
    env=os.environ.copy()
    env.update({"MODEL_PATH":str(ROOT/"artifacts/model.pt"),"MODEL_VERSION":"1.0.0","PORT":"8000",
                "OMP_NUM_THREADS":"2","PYTHONUNBUFFERED":"1"})
    start=time.monotonic()
    log=(LOGS/"local-server.log").open("w",encoding="utf-8")
    proc=subprocess.Popen([python,"-m","uvicorn","src.api:app","--host","127.0.0.1","--port","8000"],
                          env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    try:
        first_successful_health()
        cold=round(time.monotonic()-start,3)
        info=smoke("local")
        result=benchmark_run("http://127.0.0.1:8000",ROOT/"artifacts/samples/yes.wav")
        memory=local_rss_mb(proc.pid)
        accurate=local_evaluation(python)
        output={"environment":"Локально (venv, Ubuntu runner)","accuracy":accurate["accuracy_pct"],
                "model_size_kb":info["model_size_kb"],
                "server_ms":result["server_ms"],"client_ms":result["client_ms"],
                "requests":result["requests"],"warmups":result["warmups"],
                "environment_mb":float(run(["du","-sm",venv]).split()[0]),
                "ram_mb":memory,"cold_start_s":cold,"test_count":accurate["count"]}
        print(json.dumps(output,ensure_ascii=False),flush=True)
        return output
    finally:
        proc.terminate()
        try: proc.wait(timeout=8)
        except subprocess.TimeoutExpired: proc.kill()
        log.close()

def measure_docker(label,tag):
    name="kws_"+label
    run(["docker","rm","-f",name],check=False)
    start=time.monotonic()
    run(["docker","run","-d","--name",name,"-p","8000:8000",tag],
        "docker-run-"+label+".log")
    try:
        first_successful_health()
        cold=round(time.monotonic()-start,3)
        wait_docker_healthy(name)
        (LOGS/("ps-"+label+".log")).write_text(
            "docker ps --filter name="+name+"\n"+
            run(["docker","ps","--filter","name="+name]),encoding="utf-8")
        info=smoke(label)
        bench=benchmark_run("http://127.0.0.1:8000",ROOT/"artifacts/samples/yes.wav")
        accurate=docker_evaluation(name)
        memory=docker_mem_mb(name)
        run(["docker","logs",name],"server-"+label+".log")
        output={"environment":"Docker ("+label+"-stage)","accuracy":accurate["accuracy_pct"],
                "model_size_kb":info["model_size_kb"],
                "server_ms":bench["server_ms"],"client_ms":bench["client_ms"],
                "requests":bench["requests"],"warmups":bench["warmups"],
                "environment_mb":bytes_to_mb(image_bytes(tag)),
                "ram_mb":memory,"cold_start_s":cold,"test_count":accurate["count"]}
        print(json.dumps(output,ensure_ascii=False),flush=True)
        return output
    finally:
        run(["docker","rm","-f",name],check=False)

def main():
    print("=== LAB2 — DOCKER MLOPS — REAL RUN ===",flush=True)
    print(run(["df","-h","."], "disk-initial.log"))
    tag_multi="kws-api:1.0.0"
    tag_single="kws-api:1.0.0-single"
    sha=os.environ.get("GITHUB_SHA","local")[:12]
    buildargs=["--build-arg","EPOCHS=6","--build-arg","MAX_PER_CLASS=500",
               "--build-arg","MODEL_VERSION=1.0.0","--build-arg","GIT_COMMIT="+sha]
    run(["docker","build","--progress=plain","-f","Dockerfile","-t",tag_multi,*buildargs,"."],
        "build-multi.log")
    run(["docker","build","--progress=plain","-f","Dockerfile.single","-t",tag_single,*buildargs,"."],
        "build-single.log")
    run(["docker","images","kws-api"],"docker-images.log")
    run(["docker","history","--no-trunc",tag_multi],"history-multi.log")
    run(["docker","history","--no-trunc",tag_single],"history-single.log")
    hashes={
        "multi":hash_model(tag_multi,"/app/artifacts/model.pt"),
        "single":hash_model(tag_single,"/build/artifacts/model.pt"),
    }
    if hashes["single"]!=hashes["multi"]:
        raise RuntimeError("Single і multi містять різні ваги. Порівняння некоректне.")
    run(["docker","rm","-f","lab2_extract"],check=False)
    run(["docker","create","--name","lab2_extract",tag_multi])
    try: run(["docker","cp","lab2_extract:/app/artifacts",str(ROOT/"artifacts")])
    finally: run(["docker","rm","-f","lab2_extract"])
    local=measure_local()
    single=measure_docker("single",tag_single)
    multi=measure_docker("multi",tag_multi)
    rows=[local,single,multi]
    assert len({round(r["accuracy"],4) for r in rows})==1, "Accuracy differs"
    assert len({r["test_count"] for r in rows})==1, "Test counts differ"
    reduction=round(100*(single["environment_mb"]-multi["environment_mb"])/single["environment_mb"],2)
    threshold=float(os.environ.get("ACC_THRESHOLD","60"))
    summary={
        "dataset":"Google mini Speech Commands; 4 classes; 500 WAV/class",
        "modalities":"audio",
        "architecture":"AudioCNN, 2 Conv2d blocks + BatchNorm + pooling + FC",
        "image_multi":tag_multi,
        "image_single":tag_single,
        "environment":"Ubuntu 24.04 GitHub Actions hosted runner; Python 3.11; CPU",
        "rows":rows,
        "model_sha256":hashes["multi"],
        "multi_stage_reduction_pct":reduction,
        "multi_stage_reduction_mb":round(single["environment_mb"]-multi["environment_mb"],2),
        "accuracy_threshold_pct":threshold,
        "quality_gate_pass":multi["accuracy"]>=threshold,
        "github_run_id":os.getenv("GITHUB_RUN_ID",""),
        "github_sha":os.getenv("GITHUB_SHA",""),
        "github_repo":os.getenv("GITHUB_REPOSITORY",""),
        "date_utc":time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime()),
    }
    (RESULTS/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("=== ПІДСУМКОВІ ФАКТИЧНІ МЕТРИКИ ===",flush=True)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    if not summary["quality_gate_pass"]:
        raise RuntimeError(f"Quality gate failure: accuracy {multi['accuracy']} < threshold {threshold}")
    print("QUALITY GATE PASSED",flush=True)

if __name__=="__main__":
    main()
