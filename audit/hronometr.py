# -*- coding: utf-8 -*-
"""Хронометраж блока: сколько времени слайды съедят в эфире.

Считает не «по 22 секунды на слайд», а по содержимому: сколько на слайде смысловых
единиц и сколько спикер над ними скажет. Темп живой речи на вебинаре — 135 слов/мин;
на слайд спикер говорит примерно вдвое больше слов, чем на нём написано, плюс пауза.

Запуск: python3 audit/hronometr.py 252 278
"""
import json, re, sys, pathlib

MAST = pathlib.Path(__file__).resolve().parent.parent / 'PREZA-EFIRA-v4.html'
src  = MAST.read_text(encoding='utf-8')
i, j = src.index('var S = ['), src.index('\n];', src.index('var S = ['))
S    = json.loads(src[i + len('var S = '):j + 2])
lo, hi = int(sys.argv[1]), int(sys.argv[2])

WPM   = 135.0        # слов в минуту живой речи
RATIO = 2.0          # спикер говорит вдвое больше, чем написано на слайде
PAUSE = 3.0          # пауза на смену слайда и вдох

def plain(h): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h or '')).strip()

rows, total = [], 0.0
for n in range(lo, hi + 1):
    s = S[n - 1]
    words = len(plain(s.get('t', '')).split()) + len(plain(s.get('b', '')).split())
    sec = words * RATIO / WPM * 60 + PAUSE
    kind = s.get('kind')
    if kind == 'scroll':                       # стоп-скролл: восемь глав, по главе на нажатие
        sec = max(sec, len(s.get('chap') or s.get('beats') or []) * 9 + PAUSE)
    if kind == 'video':
        sec = max(sec, 20)
    if (s.get('lv') or 0) >= 10: sec += 8      # пик держим дольше
    if 'tcq' in (s.get('b') or ''): sec += 10  # чип «напишите в чат» — ждём реакцию зала
    total += sec
    rows.append((n, sec, s.get('dirk') or '—', s.get('t', ''), words))

print(f'{"#":>4} {"сек":>5}  {"слов":>5}  слайд')
for n, sec, dirk, t, w in rows:
    mark = ' ←' if sec > 45 else ''
    print(f'{n:>4} {sec:>5.0f}  {w:>5}  {t[:52]}{mark}')
print(f'\nвсего: {total/60:.1f} мин на {len(rows)} слайдов · в среднем {total/len(rows):.0f} с на слайд')
print(f'запас до 10 минут: {600 - total:+.0f} с')
heavy = sorted(rows, key=lambda r: -r[1])[:6]
print('\nсамые дорогие по времени:')
for n, sec, dirk, t, w in heavy:
    print(f'  #{n} {sec:>5.0f} с · {t[:48]}')
