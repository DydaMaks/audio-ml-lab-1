"""Генерує читабельні зображення справжніх локальних журналів перевірки.
Ці знімки НЕ є журналами GitHub Actions та НЕ доводять запуск Docker.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
P=Path(__file__).resolve().parent
MONO='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
SANS='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
for log,title,out in [
 ('LOCAL_UNIT_TESTS_NOT_DOCKER.txt','ЛОКАЛЬНІ МОДУЛЬНІ ТЕСТИ — НЕ DOCKER','01-local-unit-test.png'),
 ('LOCAL_API_SMOKE_NOT_DOCKER.txt','ЛОКАЛЬНА ПЕРЕВІРКА API — НЕ DOCKER','02-local-api-smoke.png')
]:
    rows=(P/log).read_text(encoding='utf-8').splitlines()
    im=Image.new('RGB',(1420,200+len(rows)*42),'#0f1723');d=ImageDraw.Draw(im)
    d.rounded_rectangle((18,17,1402,im.height-17),radius=14,outline='#334a5c',width=3)
    d.rounded_rectangle((22,20,1398,116),radius=12,fill='#1e3044')
    d.text((50,43),title,font=ImageFont.truetype(BOLD,26),fill='white')
    d.text((50,81),'Оригінальний вивід із локального середовища; не результати навчання на Google Speech Commands.',font=ImageFont.truetype(SANS,14),fill='#c9dbed')
    for i,line in enumerate(rows):
      if len(line)>133:
         line=line[:130]+'...'
      d.text((50,145+i*42),line,font=ImageFont.truetype(MONO,17),fill='#dce8f4')
    im.save(P/out)
