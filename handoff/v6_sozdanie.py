# -*- coding: utf-8 -*-
"""v6 — отдельная дека только из продающей части: акт 8 (до кнопки) и акт 9 (дожим).

Влад: «сделай всё в новой версии 6, оставь только продающую часть — и полностью
сделай продающую и дожимную». v4 не трогаем.

Берём из мастера слайды #282 «Два пути» → #385 (конец), режем на два акта по кнопке,
переопределяем ACTS, чистим прогресс-полосу от чужих актов.
"""
import json, re, shutil, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC  = ROOT / 'PREZA-EFIRA-v4.html'
DST  = ROOT / 'PREZA-EFIRA-v6.html'
APPLY = '--apply' in sys.argv

src = SRC.read_text(encoding='utf-8')
i, j   = src.index('var S = ['), src.index('\n];', src.index('var S = ['))
arr    = json.loads(src[i + len('var S = '):j + 2])
i2, j2 = src.index('var DIR = '), src.index('\n};', src.index('var DIR = '))
DIR    = json.loads(src[i2 + len('var DIR = '):j2 + 2])
i3, j3 = src.index('var ACTS = '), src.index('\n];', src.index('var ACTS = '))

def plain(h): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h or '')).strip()

start = next(k for k, s in enumerate(arr) if s.get('dirk') == 'Два пути')
cta   = next(k for k, s in enumerate(arr) if s.get('kind') == 'cta')
sub   = [json.loads(json.dumps(s)) for s in arr[start:]]

for k, s in enumerate(sub):
    s['a'] = 0 if k <= (cta - start) else 1          # 0 = акт 8, 1 = акт 9 дожим

titles = {plain(s.get('t', '')) for s in sub if s.get('t')}
DIR6 = {k: v for k, v in DIR.items() if k in titles}

ACTS6 = ['Акт 8 · Продающая часть · 80:00–100:00', 'Акт 9 · Дожим · от 100:00']

print(f'взято из v4: #{start + 1}–#{len(arr)} = {len(sub)} слайдов')
print(f'  акт 8 (до кнопки включительно): {sum(1 for s in sub if s["a"] == 0)} слайдов')
print(f'  акт 9 (дожим):                  {sum(1 for s in sub if s["a"] == 1)} слайдов')
print(f'  DIR перенесено: {len(DIR6)} записей')

if not APPLY:
    print('\nпредпросмотр. Запись — с флагом --apply'); sys.exit(0)

# в файле порядок объявлений: ACTS → S → DIR. Собираем строго по позициям,
# иначе срезы перекрываются и блок дублируется (поймано на первой сборке v6).
parts = sorted([(i3, j3, 'var ACTS = ', ACTS6), (i, j, 'var S = ', sub), (i2, j2, 'var DIR = ', DIR6)])
out, cur = '', 0
for a, b, head, data in parts:
    out += src[cur:a + len(head)] + json.dumps(data, ensure_ascii=False, indent=1)
    cur = b + 2
out += src[cur:]
out = out.replace('<title>', '<title>v6 · ', 1) if '<title>' in out else out
DST.write_text(out, encoding='utf-8')
print(f'\nсоздано → {DST.name} ({DST.stat().st_size // 1024} КБ)')
