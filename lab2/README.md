# Лабораторна робота №2 — MLOps / Docker
Проєкт продовжує ЛР №1 і використовує Google mini Speech Commands (yes/no/up/down), Mel-спектрограму 64×101 та AudioCNN.

- `Dockerfile`: двоетапна збірка trainer/runtime, модель включена у фінальний образ; повна тестова вибірка залишається поза runtime-образом.
- `Dockerfile.single`: для порівняння — один важкий образ, що містить інструменти навчання й дані.
- `src/api.py`: GET /health, GET /model-info, POST /predict.
- `src/evaluate.py`: фактична Accuracy на незалежній тестовій вибірці.
- `scripts/benchmark.py`: 10 warmups + 100 запитів, mean/p50/p95 серверної та клієнтської latency.
- `scripts/ci.py`: автоматичні вимірювання local venv і Docker single/multi в одній хмарній Ubuntu-машині.
- `reporting/make_report.py`: автоматичний DOCX/PDF зі справжніх CI-логів та метрик.

Запуск із кореня репозиторію: `docker build -t kws-api:multi lab2` (потребує Docker і дискового місця).
Для ноутбука з малим диском: GitHub Actions / вкладка Actions / workflow «Lab2 MLOps Docker»; завантажити DOCX/PDF у Artifacts.

**Уточнення:** порівняння «без Docker» проводиться в Python venv на GitHub Ubuntu runner, а не на Windows-ноутбуці. Всі числові результати формуються тільки після реального виконання; значення не зафіксовані заздалегідь.
