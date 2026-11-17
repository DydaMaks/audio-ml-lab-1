#!/usr/bin/env python3
"""Фінальний звіт лише з ФАКТИЧНИХ результатів GitHub Actions."""
from __future__ import annotations
import html
import json
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                               Image as PdfImage, Table, TableStyle, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"
LOGS=OUT/"logs"
EVIDENCE=OUT/"evidence"
REPORTS=OUT/"reports"
EVIDENCE.mkdir(parents=True,exist_ok=True)
REPORTS.mkdir(parents=True,exist_ok=True)
source=OUT/"summary.json"
if not source.exists():
    raise RuntimeError("Немає фактичних метрик. Вигадані результати заборонені.")
d=json.loads(source.read_text(encoding="utf-8"))
rows=d["rows"]
assert len(rows)==3 and all(r["requests"]>=100 and r["warmups"]>=10 for r in rows)
run_url="https://github.com/"+d["github_repo"]+"/actions/runs/"+str(d["github_run_id"])
repo_url="https://github.com/"+d["github_repo"]+"/tree/lab2-mlops/lab2"

def fontfile(mono=False,bold=False):
    candidates=(
        ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf"]
        if mono else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for filename in candidates:
        if Path(filename).exists(): return filename
    raise FileNotFoundError("Системні шрифти для української мови не знайдено.")

def render_log(logfile,outfile,title,tail=21):
    path=LOGS/logfile
    if not path.exists(): raise FileNotFoundError("Відсутній журнал: "+str(path))
    content=path.read_text(encoding="utf-8",errors="replace")
    content=re.sub(r"\x1b\[[0-9;]*m","",content)
    lines=[x.rstrip() for x in content.splitlines() if x.strip()][-tail:]
    # Чесний рендеринг реального stdout: зображення журналу, не скриншот вікна UI.
    formatted=[]
    for line in lines:
        formatted.extend(textwrap.wrap(line,110,break_long_words=True,replace_whitespace=False)[:3])
    formatted=formatted[-28:]
    width=1600
    height=175+len(formatted)*27+34
    image=Image.new("RGB",(width,height),"#0b1220")
    p=ImageDraw.Draw(image)
    p.rectangle((0,0,width,112),fill="#1c2b3f")
    head=ImageFont.truetype(fontfile(bold=True),27)
    mono=ImageFont.truetype(fontfile(mono=True),17)
    small=ImageFont.truetype(fontfile(),15)
    p.text((42,30),title,font=head,fill="#ffffff")
    p.text((42,78),"Фрагмент фактичного журналу GitHub Actions / "+logfile,
           font=small,fill="#a8bfd6")
    for i,line in enumerate(formatted):
        p.text((34,143+i*27),line,font=mono,fill="#d5e2eb")
    target=EVIDENCE/outfile
    image.save(target)
    return target

pictures=[
    ("build-multi.log","01-build-multi.png","Збирання multi-stage Docker",21),
    ("build-single.log","02-build-single.png","Збирання single-stage Docker",17),
    ("docker-images.log","03-images.png","Розміри Docker-образів",15),
    ("ps-multi.log","04-docker-ps.png","Docker ps / стан healthy",15),
    ("smoke-multi.log","05-api.png","Реальні відповіді REST API",20),
    ("stats-kws_multi.log","06-docker-stats.png","Використання RAM / Docker stats",15),
    ("history-single.log","07-history-single.png","Історія шарів single-stage",16),
    ("history-multi.log","08-history-multi.png","Історія шарів multi-stage",16),
]
images=[]
for name,filename,title,tail in pictures:
    images.append((render_log(name,filename,title,tail),title))

def fmt(x,precision=2):
    return "—" if x is None else f"{x:.{precision}f}".replace(".",",")

def comparison_rows():
    result=[]
    for row in rows:
        result.append([
            row["environment"],
            "CNN",
            fmt(row["model_size_kb"]),
            fmt(row["accuracy"]),
            fmt(row["server_ms"]["mean"])+"/"+fmt(row["server_ms"]["p95"]),
            fmt(row["client_ms"]["mean"])+"/"+fmt(row["client_ms"]["p95"]),
            fmt(row["environment_mb"]),
            fmt(row["ram_mb"]),
            fmt(row["cold_start_s"]),
        ])
    return result

def codes(path):
    return (ROOT/path).read_text(encoding="utf-8")

dockerfile=codes("Dockerfile")
ignored=codes(".dockerignore")
req_api=codes("requirements-api.txt")
req_train=codes("requirements-train.txt")
single=rows[1]
multi=rows[2]
overhead=round(multi["client_ms"]["mean"]-rows[0]["client_ms"]["mean"],3)
model_size=rows[2]["model_size_kb"]
accuracy=rows[2]["accuracy"]

# ---------- WORD ----------
doc=Document()
sec=doc.sections[0]
sec.top_margin=Cm(2)
sec.bottom_margin=Cm(1.7)
sec.left_margin=Cm(2.2)
sec.right_margin=Cm(1.9)
normal=doc.styles["Normal"]
normal.font.name="Times New Roman"
normal.font.size=Pt(11)
normal.paragraph_format.space_after=Pt(5)
for name in ("Heading 1","Heading 2"):
    sty=doc.styles[name]
    sty.font.name="Times New Roman"
    sty.font.size=Pt(14 if name=="Heading 1" else 12)
    sty.font.bold=True
    sty.font.color.rgb=RGBColor(28,49,76)

def para(t="",center=False,bold=False):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    run=p.add_run(str(t));run.bold=bold
    return p

def head(t):doc.add_heading(t,level=1)

def code(t):
    for line in t.splitlines():
        p=doc.add_paragraph()
        p.paragraph_format.space_after=Pt(0)
        p.paragraph_format.line_spacing=1
        run=p.add_run(line if line else " ")
        run.font.name="Consolas"
        run.font.size=Pt(7.5)

def picture(path,cap):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path),width=Cm(15.7))
    p=para(cap,center=True)
    for r in p.runs:r.italic=True;r.font.size=Pt(8)

def table(header,data):
    t=doc.add_table(rows=1,cols=len(header))
    t.style="Table Grid"
    for j,h in enumerate(header):t.rows[0].cells[j].text=str(h)
    for row in data:
        cells=t.add_row().cells
        for j,v in enumerate(row):cells[j].text=str(v)
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:r.font.size=Pt(7.1)
    doc.add_paragraph()

for t in ["Міністерство освіти і науки України",
          "Львівський національний університет імені Івана Франка",
          "Факультет електроніки та комп’ютерних технологій"]:
    para(t,center=True)
doc.add_paragraph("\n\n\n\n")
para("ЛАБОРАТОРНА РОБОТА № 2",center=True,bold=True)
para("З курсу «Проєкт з інтеграції інформаційних систем»",center=True)
para("Контейнеризація та розгортання ML-моделі з Docker",center=True)
para("(базовий рівень)",center=True)
doc.add_paragraph("\n\n\n")
para("Виконав: студент групи ФЕІ-44 Дида Максим")
para("Викладач: асистент Прокопів Роман Володимирович")
doc.add_paragraph("\n")
para("Львів — 2026",center=True)
doc.add_page_break()

head("Мета роботи")
para("Контейнеризувати аудіокласифікатор із лабораторної роботи №1, розділити навчання й інференс через multi-stage Docker, порівняти роботу в Python venv та двох типах Docker-образів за основними метриками й налаштувати автоматичне тестування у GitHub Actions.")
para("Порівняння виконано на одній хмарній машині GitHub Actions (Ubuntu 24.04). «Локально» означає запуск без Docker у venv на тому самому runner; це не вимірювання на Windows-ноутбуці.")
head("1. Датасет і ML-модель")
para(f"Google mini Speech Commands, класи yes/no/up/down, по 500 WAV на клас. Моно, 16 кГц, 1 секунда, логарифмічна Mel-спектрограма (64 смуги, форма 1×64×101). AudioCNN: два блоки Conv2d, BatchNorm, ReLU, MaxPool, AdaptiveAvgPool та два повнозв'язні шари. Навчання: 6 епох, Adam, seed 42.")
para(f"Тестова точність: {fmt(accuracy)}% на {rows[2]['test_count']} зразках. Файл ваг: {fmt(model_size)} КБ. Для всіх трьох порівнянь використано той самий SHA-256 файлу ваг: {d['model_sha256']}.")
head("2. Структура проєкту")
code("lab2/\n├── src/               data.py, model.py, train.py, evaluate.py, api.py, healthcheck.py\n├── scripts/           ci.py, benchmark.py\n├── reporting/         make_report.py\n├── artifacts/         model.pt, labels.json, metrics.json, samples/, testset/ (генеруються)\n├── requirements-train.txt, requirements-api.txt\n├── Dockerfile, Dockerfile.single, .dockerignore, README.md\n└── results/           метрики, логи, зображення та звіт (генеруються)")
head("3. Dockerfile (multi-stage)")
para("Етап trainer завантажує датасет, встановлює пакети PyTorch та навчає AudioCNN. Етап runtime починається з чистого python:3.11-slim, копіює тільки потрібний код та artifacts/, запускає FastAPI не від root і перевіряє /health. Версії залежностей зафіксовано.")
code(dockerfile)
doc.add_page_break()
head("4. .dockerignore та залежності")
para("Файл .dockerignore запобігає копіюванню даних, віртуального середовища та інших зайвих файлів у Docker build context.")
code(ignored)
para("requirements-train.txt:")
code(req_train)
para("requirements-api.txt:")
code(req_api)
head("5. REST API")
para("GET /health повертає статус сервісу. GET /model-info повертає архітектуру, перелік класів, версію, розмір і Accuracy. POST /predict приймає WAV і повертає label, confidence, probabilities, latency_ms та model_version. Модель завантажується один раз під час запуску; некоректний WAV повертає 400.")
head("6. Збирання та запуск")
para("Зібрано два Docker-образи, перевірено docker images, docker ps зі статусом healthy, відповіді API та docker stats. Зображення нижче є точним рендерингом фрагментів фактичних текстових журналів CI, а не імітацією скриншотів Docker Desktop.")
for i in [0,1,2,3,4,5]:
    picture(images[i][0],f"Рисунок {i+1}. {images[i][1]}.")
head("7. Вимірювання та порівняння")
para("Для кожного середовища виконано 10 прогрівних і 100 основних HTTP-запитів з однаковим WAV. Latency (сервер) вимірює препроцесинг та інференс; latency (клієнт) — повний HTTP-запит. Наведено середні значення та p95. RAM виміряно за RSS (venv) і docker stats (Docker). Холодний старт — від запуску сервісу до першого успішного /health.")
table(["Середовище","Модель","КБ","Acc.%","Сервер mean/p95, мс","Клієнт mean/p95, мс","МБ","RAM, МБ","Старт, с"],comparison_rows())
para(f"Multi-stage образ менший за single-stage на {fmt(d['multi_stage_reduction_mb'])} МБ ({fmt(d['multi_stage_reduction_pct'])}%). Різниця середньої клієнтської затримки між multi-stage Docker та venv становила {fmt(overhead,3)} мс. Порівнювалися однакові ваги моделі; зміна контейнеризації не змінювала точність.")
head("8. Історія шарів Docker")
para("За docker history найбільше місця займають установлення PyTorch та пов'язаних залежностей. У single-stage залишаються й інструменти навчання, і вибірка. Multi-stage залишає датасет і навчальні шари в trainer та пакує лише файли ваг, мітки й метрики. Для оцінки accuracy тестові WAV додаються як read-only volume.")
for i in [6,7]:picture(images[i][0],f"Рисунок {i+1}. {images[i][1]}.")
head("9. CI-пайплайн")
para(f"GitHub Actions: checkout → перевірка синтаксису → build multi-stage/single-stage → запуск контейнерів → /health, /model-info, /predict → 100-запитний benchmark → оцінка accuracy → quality gate ({fmt(d['accuracy_threshold_pct'])}% мінімум) → формування звіту.")
para("Фактичний запуск: "+run_url)
para("Вихідний код: "+repo_url)
head("Висновки")
para(f"У лабораторній роботі розгорнуто аудіокласифікатор AudioCNN у відтворюваному Docker-образі та реалізовано multi-stage збірку. Порівняння виконано для venv, single-stage Docker і multi-stage Docker з однаковими вагами, {rows[2]['test_count']} тестовими зразками й 100 запитами в кожному середовищі. Test Accuracy дорівнювала {fmt(accuracy)}%, а використання multi-stage зменшило розмір образу на {fmt(d['multi_stage_reduction_pct'])}% ({fmt(d['multi_stage_reduction_mb'])} МБ). Автоматизований CI перевірив доступність API, коректну обробку помилок, точність і затримки, що забезпечує відтворюваний базовий цикл MLOps.")
word=REPORTS/"Звіт_ЛР2_Дида_Максим_MLOps_Docker.docx"
doc.save(word)

# ---------- PDF з тих самих реальних даних ----------
pdfmetrics.registerFont(TTFont("DejaVuUA",fontfile()))
pdfmetrics.registerFont(TTFont("DejaVuUABold",fontfile(bold=True)))
styles={
"body":ParagraphStyle("body",fontName="DejaVuUA",fontSize=9.0,leading=14,spaceAfter=8),
"h":ParagraphStyle("head",fontName="DejaVuUABold",fontSize=12.5,leading=18,spaceBefore=10,spaceAfter=10),
"title":ParagraphStyle("title",fontName="DejaVuUABold",fontSize=17,leading=25,alignment=1),
"tiny":ParagraphStyle("tiny",fontName="DejaVuUA",fontSize=6.8,leading=9.3),
"code":ParagraphStyle("code",fontName="Courier",fontSize=6.2,leading=8,spaceAfter=0),
"cap":ParagraphStyle("caption",fontName="DejaVuUA",fontSize=8,leading=11,alignment=1,spaceAfter=10),
}
story=[]
def add(t,style="body"):story.append(Paragraph(html.escape(str(t)),styles[style]))
def h(t):add(t,"h")
def pic(i):
    path,label=images[i]
    with Image.open(path) as im:
        w,hh=im.size
    width=15.9*cm
    story.append(PdfImage(str(path),width=width,height=width*hh/w))
    add("Рисунок "+str(i+1)+". "+label,"cap")
def code_pdf(t):
    for line in t.splitlines():
        # Кожен рядок є окремим параграфом, отже PDF автоматично переносить сторінки.
        for part in textwrap.wrap(line,100,replace_whitespace=False,drop_whitespace=False) or [""]:
            story.append(Paragraph(html.escape(part).replace(" ","&#160;") or "&#160;",styles["code"]))
def metric_table():
    headers=["Середовище","Acc.%","КБ","Сервер mean/p95","Клієнт mean/p95","Образ / venv МБ","RAM МБ","Старт с"]
    data=[[Paragraph(html.escape(str(x)),styles["tiny"]) for x in headers]]
    for x in rows:
        cells=[x["environment"],fmt(x["accuracy"]),fmt(x["model_size_kb"]),
               fmt(x["server_ms"]["mean"])+"/"+fmt(x["server_ms"]["p95"]),
               fmt(x["client_ms"]["mean"])+"/"+fmt(x["client_ms"]["p95"]),
               fmt(x["environment_mb"]),fmt(x["ram_mb"]),fmt(x["cold_start_s"])]
        data.append([Paragraph(html.escape(str(a)),styles["tiny"]) for a in cells])
    widths=[105,37,34,60,61,67,43,42]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#a5b0bc")),
                          ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e1ebf5")),
                          ("VALIGN",(0,0),(-1,-1),"TOP"),
                          ("LEFTPADDING",(0,0),(-1,-1),3),
                          ("RIGHTPADDING",(0,0),(-1,-1),3)]))
    story.append(t)
story.append(Spacer(1,2.4*cm))
for line in ["Міністерство освіти і науки України","Львівський національний університет імені Івана Франка",
             "Факультет електроніки та комп'ютерних технологій"]: add(line,"cap")
story.append(Spacer(1,3*cm))
add("ЛАБОРАТОРНА РОБОТА № 2","title")
add("Проєкт з інтеграції інформаційних систем","title")
add("MLOps: контейнеризація AudioCNN у Docker","title")
story.append(Spacer(1,4*cm))
add("Виконав: студент групи ФЕІ-44 Дида Максим")
add("Викладач: асистент Прокопів Роман Володимирович")
story.append(Spacer(1,1*cm))
add("Львів — 2026","cap")
story.append(PageBreak())
h("Мета та умови проведення")
add("Створити відтворюваний multi-stage Docker-образ, порівняти з single-stage і Python venv, налаштувати CI та quality gate. Локальний запуск без Docker виконано в Ubuntu venv на тому самому хмарному GitHub Actions runner, а не на Windows-ноутбуці.")
h("1. Модель і дані")
add("Google mini Speech Commands: yes/no/up/down, 2000 WAV; 16 кГц, моно, 1 с, Mel-спектрограма 64×101. AudioCNN, 2 згорткові блоки, 6 епох, Adam, seed 42.")
add("Точність "+fmt(accuracy)+"% на "+str(rows[2]["test_count"])+" тестових WAV; розмір моделі "+fmt(model_size)+" КБ.")
h("2. Структура проєкту")
code_pdf("lab2/src/: data.py, model.py, train.py, evaluate.py, api.py, healthcheck.py\nlab2/scripts/: benchmark.py, ci.py\nlab2/reporting/: make_report.py\nDockerfile, Dockerfile.single, .dockerignore, requirements-train.txt, requirements-api.txt")
h("3. Повний Dockerfile (multi-stage)")
add("Stage trainer навчає модель і створює artifacts; stage runtime містить FastAPI, залежності для інференсу та готову модель. USER appuser і HEALTHCHECK додані для базової безпеки й нагляду.")
code_pdf(dockerfile)
h("4. .dockerignore")
code_pdf(ignored)
h("5. requirements-train.txt")
code_pdf(req_train)
h("6. requirements-api.txt")
code_pdf(req_api)
h("7. REST API")
add("GET /health, GET /model-info, POST /predict. Відповідь містить label, confidence, probabilities, latency_ms і model_version. Некоректні WAV повертають HTTP 400.")
h("8. Docker build, images, ps, Swagger/API та RAM")
add("Наведені зображення є рендерами фрагментів реального stdout GitHub Actions. Це не знімки Docker Desktop.")
for i in range(6):pic(i)
h("9. Порівняння")
add("10 warmup + 100 однакових запитів POST /predict у кожному середовищі; mean та p95 мілісекунд для серверного і повного клієнтського часу.")
metric_table()
story.append(Spacer(1,0.4*cm))
add("Multi-stage образ менший на "+fmt(d["multi_stage_reduction_mb"])+" МБ ("+fmt(d["multi_stage_reduction_pct"])+"%). У всіх трьох середовищах модель має однаковий SHA-256 і Accuracy.")
h("10. docker history")
add("Найбільші шари — встановлення PyTorch. Single-stage містить датасет та навчальні залежності, а multi-stage переносить лише файли моделі й метрик у runtime. Тестова вибірка для evaluate монтується як read-only volume.")
for i in (6,7):pic(i)
h("11. GitHub Actions")
add("CI автоматично збирає образи, тестує /health, /model-info, /predict, запускає benchmark, перевіряє Accuracy та формує звіт. Поріг accuracy: "+fmt(d["accuracy_threshold_pct"])+"%.")
add("Успішний CI запускається за посиланням: "+run_url)
add("Репозиторій: "+repo_url)
h("Висновки")
add("Створено Docker-образи для AudioCNN та проведено реальне порівняння в Python venv і single/multi-stage Docker. Точність моделі на тестовій вибірці становила "+fmt(accuracy)+"%, використання multi-stage зменшило розмір образу на "+fmt(d["multi_stage_reduction_pct"])+"%, а CI автоматично перевірив необхідні ендпоінти й якість моделі.")
pdf=REPORTS/"Звіт_ЛР2_Дида_Максим_MLOps_Docker.pdf"
SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=1.9*cm,rightMargin=1.9*cm,
                  topMargin=1.6*cm,bottomMargin=1.6*cm).build(story)
print("Згенеровано тільки з реальних логів і метрик:",word,pdf,flush=True)
