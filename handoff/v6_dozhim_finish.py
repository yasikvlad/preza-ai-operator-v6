# -*- coding: utf-8 -*-
"""v6 · дожим: доставить блоки 10 и 16 на места по ТЗ + текстовые правки."""
import json, re, shutil, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
V6 = ROOT / 'PREZA-EFIRA-v6.html'
APPLY = '--apply' in sys.argv
src = V6.read_text(encoding='utf-8')
i, j = src.index('var S = ['), src.index('\n];', src.index('var S = ['))
S = json.loads(src[i + len('var S = '):j + 2])
def d(x): return next((k for k, s in enumerate(S) if s.get('dirk') == x), None)
def grab(prefix):
    got = [s for s in S if (s.get('dirk') or '').startswith(prefix)]
    for s in got: S.remove(s)
    return got
done = []

# блоки 10 и 16 уехали в конец — ставим по ТЗ
b10 = grab('Д10 ·')
if b10:
    pos = d('CTA 4')                       # конец блока 9 «Сценарий А/Б»
    S[pos + 1:pos + 1] = b10
    done.append(f'блок 10 «Продающие AI-видео» ({len(b10)} слайда) — после блока 9')
b16 = grab('Д16 ·')
if b16:
    pos = d('Д15 · Рассрочка')
    S[pos + 1:pos + 1] = b16
    done.append(f'блок 16 «Контент и AI-аватар» ({len(b16)} слайда) — после рассрочки')

def sub(dirk, old, new, why):
    k = d(dirk)
    if k is None or old not in S[k].get('b', ''): print(f'⚠️  {dirk}: не найдено — {why}'); return
    S[k]['b'] = S[k]['b'].replace(old, new, 1); done.append(f'{dirk} — {why}')

# гарантия: снять срок 30 дней и «под запись»
k = d('Гарантия')
if k is not None:
    b = S[k]['b']
    b = re.sub(r'\s*за 30 дней\s*', ' ', b)
    b = b.replace('под запись', '').replace('  ', ' ')
    S[k]['b'] = b
    S[k]['note'] = ((S[k].get('note') or '') +
        '  ⚠️ СРОК НЕ ФИНАЛИЗИРОВАН: на слайде было 30 дней, Вова говорит 90 в договоре, '
        'в реальной оферте — 6 месяцев с даты завершения обучения. До эфира свести к одному числу.')
    done.append('Гарантия — снят срок «30 дней» и «под запись» (созвон 22:09)')

# Саша: $250 за сутки → $300 за выходные
for dk in ('Саша и Наталья', 'Кейсы внедрения'):
    k = d(dk)
    if k is None: continue
    b = S[k]['b']
    nb = b.replace('$250 за сутки', '$300 за выходные').replace('за сутки', 'за выходные')
    if nb != b:
        S[k]['b'] = nb; done.append(f'{dk} — «$250 за сутки» → «$300 за выходные» (картотека + заметка спикера)')

# половина результата: арифметика
sub('Половина результата', 'Один сайт за $250 — и бронь вместе со входом уже отбились',
    'Один сайт за $250 — и половина входа уже отбилась. Два сайта — и вход окуплен целиком',
    'починена арифметика: $250 меньше, чем $490 + $10')

# охотник: условие бонуса без привязки к набору
k = d('CTA 3')
if k is None: k = next((q for q, s in enumerate(S) if 'Готовый AI-охотник' in (s.get('b') or '')), None)
if k is not None:
    b = S[k]['b']
    nb = b.replace('Первым 20 броням этого эфира · Silver и Gold', 'Первым 20 броням этого эфира')
    if nb != b:
        S[k]['b'] = nb
        S[k]['note'] = ((S[k].get('note') or '') +
            '  Привязку к Silver и Gold проговариваем на звонке: в момент брони набор ещё не выбран '
            '(это прямо сказано на «после брони» и «не набор, а решение»).')
        done.append('Охотник — «первым 20 броням» без привязки к набору')

for s in S:
    if s.get('a') != 0: s['a'] = 1
akt8 = sum(1 for s in S if s.get('a') == 0)
print('\n'.join('✅ ' + x for x in done))
print(f'\nv6: {len(S)} слайдов · акт 8 — {akt8} · дожим — {len(S) - akt8}')
if not APPLY: print('\nпредпросмотр. Запись — с флагом --apply'); sys.exit(0)
stamp = datetime.datetime.now().strftime('%d%m-%H%M')
shutil.copy(V6, V6.with_name(f'PREZA-EFIRA-v6.pered-finishem-{stamp}.html'))
V6.write_text(src[:i + len('var S = ')] + json.dumps(S, ensure_ascii=False, indent=1) + src[j + 2:], encoding='utf-8')
print(f'записано. бэкап → PREZA-EFIRA-v6.pered-finishem-{stamp}.html')
