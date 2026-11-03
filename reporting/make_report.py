#!/usr/bin/env python3
"""Створення DOCX/PDF та зображень ФАКТИЧНИХ логів CI після успішного запуску.

Скриншоти тут — точне візуальне відтворення реального stdout із CI,
а НЕ підроблені знімки GitHub Actions або Docker Desktop.
Якщо метрик немає, звіт не створюється, щоб не вигадувати результатів.
"""
from __future__ import annotations

import json
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
                                Table as RLTable, TableStyle, PageBreak, KeepTogether)

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / 'metrics'
EVIDENCE = ROOT / 'evidence'
REPORTS = ROOT / 'reports'
EVIDENCE.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
training_path = METRICS / 'training.json'
api_path = METRICS / 'api_benchmark.json'
if not training_path.exists() or not api_path.exists():
    raise RuntimeError('Неможливо формувати звіт без фактичних training.json та api_benchmark.json')
training = json.loads(training_path.read_text(encoding='utf-8'))
api = json.loads(api_path.read_text(encoding='utf-8'))
assert api['requests'] == 5 and len(api['results']) == 5

GITHUB_RUN_ID = os.environ.get('GITHUB_RUN_ID', 'локальний запуск генератора')
GITHUB_SHA = os.environ.get('GITHUB_SHA', 'невідомий')
GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY', 'невідомий')
GITHUB_RUN_URL = (f'https://github.com/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}'
                  if GITHUB_REPOSITORY != 'невідомий' and GITHUB_RUN_ID != 'локальний запуск генератора' else 'локальний запуск')
DATE = datetime.now(timezone.utc).strftime('%d.%m.%Y')


def font_path(mono=False, bold=False):
    names = ([
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
    ] if mono else [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ])
    for name in names:
        if Path(name).exists(): return name
    raise FileNotFoundError('Немає системних DejaVu шрифтів')


def snapshot(log_name, target, title, tail=32):
    source = METRICS / log_name
    if not source.exists():
        raise FileNotFoundError(f'Відсутній фактичний журнал: {source}')
    text = source.read_text(encoding='utf-8', errors='replace')
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    cleaned = [re.sub(r'\s+$','', line) for line in text.splitlines()]
    cleaned = [line for line in cleaned if line.strip()]
    cleaned = cleaned[-tail:]
    lines = []
    for line in cleaned:
        lines += textwrap.wrap(line, width=112, break_long_words=True, replace_whitespace=False) or ['']
    width, line_h = 1600, 25
    pad_top = 145
    height = max(300, pad_top + len(lines) * line_h + 45)
    im = Image.new('RGB', (width, height), '#101924')
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(font_path(mono=True), 17)
    head_font = ImageFont.truetype(font_path(bold=True), 26)
    sub_font = ImageFont.truetype(font_path(), 16)
    d.rounded_rectangle((21, 18, width-21, height-18), 17, fill='#101924', outline='#36536a', width=3)
    d.rounded_rectangle((23, 20, width-23, 108), 12, fill='#1c2e41')
    d.text((52, 38), title, font=head_font, fill='#ffffff')
    d.text((52, 76), f'Фрагмент реального журналу CI: {log_name}. Дата UTC: {DATE}', font=sub_font, fill='#b8c8d9')
    for i, line in enumerate(lines):
        d.text((51, pad_top+i*line_h), line, font=f, fill='#d8e4ef')
    im.save(EVIDENCE / target)
    return EVIDENCE / target

img_train = snapshot('ci-training.log', '01-training-log.png', 'Docker · навчання AudioCNN', 27)
img_ps = snapshot('ci-docker-ps.log', '02-docker-containers.png', 'Docker Compose · запущені контейнери', 24)
img_api = snapshot('ci-api-tests.log', '03-rest-api-tests.png', 'Docker · тестові REST-запити', 26)

# ------------------------- DOCX ---------------------------------------
doc = Document()
section = doc.sections[0]
section.top_margin = Cm(2.0)
section.bottom_margin = Cm(1.9)
section.left_margin = Cm(2.3)
section.right_margin = Cm(2.0)
normal = doc.styles['Normal']
normal.font.name = 'Times New Roman'
normal.font.size = Pt(12)
normal.paragraph_format.space_after = Pt(6)
for name, size in [('Heading 1',15), ('Heading 2',13)]:
    sty=doc.styles[name]
    sty.font.name='Times New Roman'; sty.font.size=Pt(size);sty.font.bold=True
    sty.font.color.rgb=RGBColor(25,56,79)


def para(text='', center=False, bold=False):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    r=p.add_run(text);r.bold=bold
    return p


def addtable(headers, rows):
    t=doc.add_table(rows=1, cols=len(headers));t.style='Table Grid'
    for j,name in enumerate(headers): t.rows[0].cells[j].text=str(name)
    for row in rows:
        cells=t.add_row().cells
        for j,val in enumerate(row): cells[j].text=str(val)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:r.font.size=Pt(9)
    doc.add_paragraph()


def add_img(image, caption):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(image), width=Cm(15.6))
    p=para(caption, center=True)
    for r in p.runs:r.font.size=Pt(9);r.italic=True


def new_page(): doc.add_page_break()

for text in ['Міністерство освіти і науки України',
             'Львівський національний університет імені Івана Франка',
             'Факультет електроніки та комп’ютерних технологій']:
    para(text, center=True)
doc.add_paragraph('\n\n\n')
para('ЗВІТ', center=True, bold=True)
para('до лабораторної роботи № 1', center=True, bold=True)
para('з курсу «Проєкт з інтеграції інформаційних систем»', center=True)
para('Базовий рівень: AudioCNN, Google Speech Commands, FastAPI та Docker', center=True)
doc.add_paragraph('\n\n\n')
para('Виконав: студент групи ФЕІ-44 Дида Максим', center=False)
para('Викладач: асистент Прокопів Роман Володимирович', center=False)
doc.add_paragraph('\n\n\n')
para('Львів — 2026', center=True)

new_page()
doc.add_heading('Мета та умови виконання',1)
para('Мета роботи — ознайомитися з життєвим циклом моделі машинного навчання для аудіо: підготувати дані, навчити нейронну мережу, розгорнути REST API у Docker та виміряти точність і затримку інференсу.')
para('Виконано лише базові завдання: Google Speech Commands (4 команди), Mel-спектрограми, AudioCNN на PyTorch, API на FastAPI та оцінювання у Docker. Додаткові командні завдання IMDB, веб-інтерфейс і 10 інтеграційних тестів не виконувалися.')
para('Робоча ОС студента — Windows 11. Навчання та тестування проведено в ізольованих Docker-контейнерах на віддаленому GitHub Actions runner (Ubuntu 24.04). Локально завантажувати масиви даних та Docker-образи не потрібно.')
doc.add_heading('Етап 1. Підготовка даних і навчання',1)
para('Використана публічна підмножина Google mini Speech Commands. Із класів yes, no, up, down відібрано по 500 WAV-файлів. Для кожного запису застосовано моно, частоту 16 кГц, тривалість 1 с, логарифмічну Mel-спектрограму (64 Mel-смуги).')
para('Модель AudioCNN складається з двох згорткових блоків Conv2d + BatchNorm2d + ReLU + MaxPool2d, адаптивного пулінгу та двох повнозв’язних шарів. Навчання тривало 6 епох; вибірка розподіляється за ідентифікаторами мовців між train/validation/test.')
addtable(['Характеристика', 'Фактичний результат'], [
 ('Датасет','Google mini Speech Commands, WAV'),('Класи','yes / no / up / down'),
 ('Train / validation / test',f"{training['split']['train']} / {training['split']['validation']} / {training['split']['test']}"),
 ('Параметрів моделі',training['num_parameters']),('Кількість епох',training['epochs']),
 ('Тестова точність',f"{training['accuracy_test_pct']:.2f}%"),
 ('Файл ваг',f"{training['model_size_kb']:.2f} КБ"),
])

new_page()
doc.add_heading('Журнал навчання у Docker',1)
para('Показано фрагмент фактичного stdout контейнера train, збережений автоматично під час поточного виконання GitHub Actions.')
add_img(img_train,'Рис. 1. Фактичний журнал епох і тестової точності (рендеринг stdout, без імітації UI).')
doc.add_heading('Етап 2. Контейнеризація бекенду в Docker',1)
para('Створено Dockerfile на основі python:3.11-slim із CPU-версіями PyTorch та torchaudio, бібліотекою soundfile і FastAPI. Docker Compose організовує окремі сервіси train, api, test і unit. Модель зберігається у saved_models/audio_cnn.pt; API запускається на порту 8000.')
para('Ендпоінт POST /predict приймає WAV, проводить ту саму Mel-передобробку й повертає predicted_class, confidence, probabilities і latency_ms. Ендпоінт GET /health перевіряє готовність API.')

new_page()
doc.add_heading('Перевірка Docker Compose',1)
add_img(img_ps,'Рис. 2. Фактичний стан контейнерів (рендеринг журналу docker compose ps).')
para('Взаємодію компонентів забезпечено всередині мережі Docker Compose: test викликає api за внутрішнім іменем http://api:8000, а навчений чекпойнт доступний API через монтування каталогу saved_models.')
doc.add_heading('Етап 3. Тестування REST API та Latency',1)
para('Після запуску контейнера api виконано п’ять HTTP POST-запитів з реальними WAV-файлами із тестової частини датасету. Тривалість обробки обчислюється у мілісекундах на сервері. Значення latency залежать від середовища runner і не включають мережеве завантаження файлу клієнтом.')
addtable(['№', 'Справжній WAV-файл', 'Прогноз', 'Confidence', 'Latency, мс'], [
 (i, r['file'], r['predicted_class'], f"{100*r['confidence']:.2f}%",f"{r['latency_ms']:.3f}")
 for i, r in enumerate(api['results'],start=1)])
para(f"Середня затримка п’яти вимірювань: {api['mean_latency_ms']:.3f} мс. /health: {api['health']}.")

new_page()
doc.add_heading('Фактичний журнал тестування API',1)
add_img(img_api,'Рис. 3. Результати POST /predict і час відповіді (рендеринг фактичного stdout).')
doc.add_heading('Зведена таблиця основних метрик',1)
addtable(['Показник', 'Результат'], [
 ('Датасет / модальність','Google mini Speech Commands / аудіо'),
 ('Архітектура','AudioCNN (2× Conv2d, BatchNorm, пулінг, FC)'),
 ('Розмір файлу моделі',f"{training['model_size_kb']:.2f} КБ"),
 ('Accuracy на тестовому наборі',f"{training['accuracy_test_pct']:.2f}%"),
 ('Середня latency',f"{api['mean_latency_ms']:.3f} мс"),
])
doc.add_heading('Висновки',1)
para('У лабораторній роботі реалізовано базовий цикл обробки голосових команд: підготовку WAV, перетворення у Mel-спектрограми, навчання AudioCNN і розгортання REST API у Docker. На незалежному тестовому наборі отримано точність '+f"{training['accuracy_test_pct']:.2f}%"+', а середня затримка п’яти запитів становила '+f"{api['mean_latency_ms']:.3f} мс"+'. Віддалений GitHub Actions дозволив виконати ресурсоємні етапи без завантаження датасету й Docker-образу на ноутбук.')
para(f'Джерело фактичних даних: {GITHUB_RUN_URL}')
para(f'Скорочений SHA коміту: {GITHUB_SHA[:12]}; дата формування: {DATE}.')
report_docx = REPORTS/'Звіт_Лаб1_Дида_Максим_ФАКТИЧНІ_РЕЗУЛЬТАТИ.docx'
doc.save(report_docx)

# ------------------------ PDF ---------------------------------------
pdfmetrics.registerFont(TTFont('DVS',font_path()))
pdfmetrics.registerFont(TTFont('DVS-Bold',font_path(bold=True)))
styles = {
 'body': ParagraphStyle('body', fontName='DVS', fontSize=9.7, leading=16, spaceAfter=9),
 'title': ParagraphStyle('title',fontName='DVS-Bold',fontSize=17,leading=25,alignment=1,spaceAfter=12),
 'h1':ParagraphStyle('h1',fontName='DVS-Bold',fontSize=13,leading=21,textColor=colors.HexColor('#17324d'),spaceBefore=8,spaceAfter=12),
 'caption':ParagraphStyle('caption',fontName='DVS',fontSize=8.2,leading=11,alignment=1,spaceAfter=10),
}

story=[]
def pp(t, style='body'):story.append(Paragraph(str(t).replace('&','&amp;'), styles[style]))
def hh(t):pp(t,'h1')
def tbl(headers,rows):
    rows=[[Paragraph(str(x),styles['caption']) for x in headers]] + [[Paragraph(str(x),styles['caption']) for x in row] for row in rows]
    w=(A4[0]-4.3*cm)/len(headers)
    t=RLTable(rows,colWidths=[w]*len(headers),repeatRows=1,hAlign='CENTER')
    t.setStyle(TableStyle([
      ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbe8f3')),
      ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#bacad8')),
      ('VALIGN',(0,0),(-1,-1),'TOP'),
      ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]));story.append(t);story.append(Spacer(1,0.4*cm))
def pic(path,caption):
    with Image.open(path) as im: width,height=im.size
    target_width=16*cm
    story.append(RLImage(str(path),width=target_width,height=target_width*height/width))
    pp(caption,'caption')

def page():story.append(PageBreak())

story.append(Spacer(1,3.2*cm))
for t in ['Міністерство освіти і науки України','Львівський національний університет імені Івана Франка','Факультет електроніки та комп’ютерних технологій']:
    pp(t,'caption')
story.append(Spacer(1,2.8*cm))
pp('ЗВІТ','title')
pp('до лабораторної роботи № 1','title')
pp('з курсу «Проєкт з інтеграції інформаційних систем»','title')
pp('Базовий рівень: AudioCNN / Speech Commands / Docker','title')
story.append(Spacer(1,3.2*cm))
pp('Виконав: студент групи ФЕІ-44 Дида Максим')
pp('Викладач: асистент Прокопів Роман Володимирович')
story.append(Spacer(1,1.0*cm))
pp('Львів, 2026','caption')
page()
hh('Мета та умови виконання')
pp('Реалізувати повний базовий цикл обробки аудіо: датасет Google Speech Commands, Mel-спектрограми, компактну AudioCNN, Docker API та вимірювання точності і швидкодії. Командні розширення не виконувалися.')
pp('Робоча ОС студента — Windows 11, а реальні навчання та тестування проводилися у Docker на GitHub Actions (Ubuntu 24.04).')
hh('Етап 1. Підготовка даних та навчання')
pp('Підготовлено по 500 WAV для класів yes, no, up, down. Аудіо приведено до моно, 16 кГц і 1 секунди. Використано логарифмічну Mel-спектрограму, 64 смуги. Мережа: два Conv2d-блоки з BatchNorm і пулінгом, адаптивний пулінг та повнозв’язні шари. Навчання — 6 епох.')
tbl(['Метрика','Фактичне значення'],[
('Train / validation / test',f"{training['split']['train']} / {training['split']['validation']} / {training['split']['test']}"),
('Параметрів мережі',training['num_parameters']),('Точність тестової вибірки',f"{training['accuracy_test_pct']:.2f}%"),
('Розмір збереженої моделі',f"{training['model_size_kb']:.2f} КБ")])
page()
hh('Результат навчання AudioCNN у Docker')
pic(img_train,'Рис. 1. Фрагмент справжнього журналу виконання (не імітація Docker Desktop).')
hh('Етап 2. Контейнеризація REST API')
pp('Створено Dockerfile (python:3.11-slim) з CPU-версіями PyTorch/torchaudio та FastAPI. Docker Compose визначає служби train, api, test і unit. API працює на порту 8000 та надає /health і POST /predict. Відповідь містить прогноз, впевненість і latency_ms.')
page()
hh('Робота контейнерів Docker Compose')
pic(img_ps,'Рис. 2. Стан сервісів із фактичного виводу docker compose ps.')
hh('Етап 3. Перевірка API та Latency')
pp('В контейнері test надіслано п’ять запитів POST /predict із WAV-файлами тестового набору. Сервер замірює час від декодування аудіо до отримання прогнозу.')
tbl(['№','WAV','Прогноз','Conf.','мс'],[(i,r['file'],r['predicted_class'],f"{100*r['confidence']:.1f}%",f"{r['latency_ms']:.3f}") for i,r in enumerate(api['results'],1)])
page()
hh('Фактичні результати тестування REST API')
pic(img_api,'Рис. 3. Вивід тестів API з реального журналу Docker.')
hh('Зведені результати')
tbl(['Показник','Фактичне значення'],[
 ('Датасет / модальність','Google mini Speech Commands / аудіо'),
 ('Архітектура','AudioCNN, 2×Conv2d + BatchNorm + FC'),
 ('Розмір моделі',f"{training['model_size_kb']:.2f} КБ"),
 ('Тестова accuracy',f"{training['accuracy_test_pct']:.2f}%"),
 ('Середня latency',f"{api['mean_latency_ms']:.3f} мс")])
hh('Висновки')
pp('Виконано базовий цикл обробки голосових команд від завантаження аудіо до REST API у Docker. Мережа AudioCNN продемонструвала точність '+f"{training['accuracy_test_pct']:.2f}%"+' на тестовій вибірці, а середня затримка п’яти інференсів становила '+f"{api['mean_latency_ms']:.3f} мс"+'. GitHub Actions забезпечив віддалене виконання без використання дискового простору студентського ноутбука для моделей і датасету.')
pp('Посилання на підтвердження: '+GITHUB_RUN_URL)
pp('SHA: '+GITHUB_SHA[:12]+'. Дата UTC: '+DATE)

report_pdf = REPORTS/'Звіт_Лаб1_Дида_Максим_ФАКТИЧНІ_РЕЗУЛЬТАТИ.pdf'
SimpleDocTemplate(str(report_pdf),pagesize=A4,rightMargin=2*cm,leftMargin=2.3*cm,topMargin=1.8*cm,bottomMargin=1.7*cm).build(story)
print('ЗВІТ З ФАКТИЧНИХ ДАНИХ СТВОРЕНО:')
print(report_docx)
print(report_pdf)
print('Accuracy:',training['accuracy_test_pct'],'%')
print('Latency:',api['mean_latency_ms'],'мс')
