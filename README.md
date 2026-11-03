# Лабораторна робота №1 — базовий рівень, Docker + GitHub Actions

Готовий проєкт для **Windows 11** без завантаження датасету, PyTorch і Docker-образів на ноутбук. Усі процеси **навчання, інференсу та тестування** виконуються **всередині Docker** на віддаленому GitHub runner (`ubuntu-24.04`).

## Що реалізовано

- Датасет **Google mini Speech Commands**, чотири команди: `yes`, `no`, `up`, `down`. Відбір 500 записів на команду (2 000 WAV загалом).
- Mel-спектрограма `64 × 101`, частота 16 кГц, моно, 1 с.
- PyTorch AudioCNN із двома Conv2d-блоками; 6 епох; `train`, `validation`, `test` за мовцем.
- Docker/Compose (сервіси `train`, `api`, `test`, `unit`).
- FastAPI: `POST /predict` + `GET /health`.
- Оцінка `Accuracy`, розміру ваг, 5 вимірів `Latency`, 3 модульні тести.
- Звіт `DOCX` і `PDF` **автоматично генерується лише з реальних даних**. Фрагменти логів CI перетворюються на зображення; **це не підроблені знімки GitHub/Docker UI**.

## Запуск через GitHub Actions — без встановлення програм

1. На [GitHub](https://github.com/new) створіть новий репозиторій, наприклад `audio-ml-lab-1` (public). Увімкніть **Add a README file**.
2. Відкрийте репозиторій → **Add file → Upload files**. Розпакуйте ZIP і завантажте **весь вміст** каталогу проєкту в корінь репозиторію, включно з прихованою папкою `.github/workflows/`. У вебінтерфейсі GitHub зручніше завантажити файли через VS Code Web (`.` на сторінці репозиторію) і commit, щоб зберегти `.github/`.
3. Перейдіть на **Actions → AudioCNN — базова лабораторна у Docker → Run workflow → Run workflow**. Якщо GitHub не дозволяє Actions, відкрийте Settings → Actions → General та увімкніть виконання workflows.
4. У вкладці **Actions** відкрийте успішний запуск → **Artifacts** → завантажте `audio-cnn-lab-report-*`. Всередині: `reports/*.docx`, `reports/*.pdf`, `evidence/*.png`, `metrics/*.json`, `metrics/*.log`, `saved_models/audio_cnn.pt`.
5. Усі скриншоти журналів та значення в звіті **отримуються лише після справжнього запуску** в Docker. Без успішного CI готовий звіт не з'явиться, і програма не створює вигадані результати.

> **Увага:** завантажити **zip як один файл** недостатньо. Потрібно розпакувати і додати файли, зберігши структуру. Встановлювати Docker, PyTorch чи Google Speech Commands на ноутбук не потрібно. Весь датасет (mini) близько 182 МБ завантажує віддалений runner. Вимога «60 ГБ» для цього **базового** варіанту не застосовується.

### Структура

```text
.github/workflows/audio-ml-lab.yml  # віддалений запуск
Dockerfile                           # Python + CPU torch/torchaudio
requirements.txt                     # API та тести
docker-compose.yml                   # 4 контейнери
prepare_data.py                      # скачати та відібрати дані
model.py                             # Mel-Spectrogram, AudioCNN, WAV
train.py                             # 6 епох, Accuracy, ваги
app.py                               # API /predict і /health
test_api.py                          # 5 запитів, Latency
tests/test_unit.py                   # unit-тести всередині Docker
reporting/make_report.py             # DOCX/PDF з фактичних результатів
reporting/requirements-report.txt    # lightweight бібліотеки звіту
```

## Якщо все ж потрібно локально (PowerShell)

У випадку достатнього місця на диску:

```powershell
docker compose build
docker compose run --rm unit
docker compose run --rm train
docker compose up -d api
docker compose run --rm test
docker compose down
```

**Використані посилання:** [TensorFlow Speech Commands tutorial](https://www.tensorflow.org/tutorials/audio/simple_audio), [GitHub Actions](https://docs.github.com/en/actions), [PyTorch](https://pytorch.org/), [FastAPI](https://fastapi.tiangolo.com/).
