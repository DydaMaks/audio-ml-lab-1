# Laboratory 3 — CI/CD for AudioCNN (basic individual level)
Continues lab 1 and lab 2. Dataset: Google mini Speech Commands, 500 WAVs per class (yes/no/up/down).
The `trainer` image executes training during `docker run`, writes artifacts to mounted volume; the `runtime` image is built from those artifacts. Data never needs downloading to Windows laptop.

## GitHub Actions
Workflow: `.github/workflows/ml-pipeline.yml` in repository root.
Jobs: lint → train → verify → build-push.
- PR: 5 epochs, no GHCR push.
- main push: 6 epochs, publish image.
- Manual: configurable epochs/push_image.
- Model and report artifacts transfer between jobs; verification includes independent validation examples and 100 benchmark requests after 10 warmups.

**Reproducibility:** deterministic seed 42; golden WAVs are selected from validation split (never train), specifically files the current model classifies correctly. They test prediction consistency, not independent accuracy (which comes from held-out test set).

## Local alternative (on host with Docker)
```sh
cd lab3
docker build --target trainer -t kws-trainer:ci .
mkdir -p artifacts
docker run --rm -e EPOCHS=6 -v "$PWD/artifacts:/artifacts" kws-trainer:ci
docker build --target runtime -t kws-api:ci .
docker run -d --name kws -p 8000:8000 kws-api:ci
```
