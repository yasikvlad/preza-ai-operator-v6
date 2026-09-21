# -*- coding: utf-8 -*-
"""v6 · дожим: починить позицию «После брони» и проставить номер блока в dirk каждого слайда.

Влад: «блоки непоследовательно расставлены». Проверка показала: все 21 на месте, но
«Вот что будет после брони» помечен блоком 15 и физически стоит после блока 16 —
последовательность ломается на 16 → 15 → 17. По плану этот слайд относится к блоку 1
(сразу за кнопкой, ответ тем, кто уже нажал).

Плюс: номер блока виден только в заметке спикера. Выносим его в dirk — тогда он читается
в режиссёрской полосе и в заметках PPTX, и порядок проверяется глазами.
"""
import json, re, shutil, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
V6 = ROOT / 'PREZA-EFIRA-v6.html'
APPLY = '--apply' in sys.argv
src = V6.read_text(encoding='utf-8')
i, j = src.index('var S = ['), src.index('\n];', src.index('var S = ['))
S = json.loads(src[i + len('var S = '):j + 2])
def blk(s):
    m = re.search(r'дожим · блок (\d+)', s.get('note') or '')
    return int(m.group(1)) if m else None

# 1. «После брони» → в блок 1, сразу после кнопки
k = next((q for q, s in enumerate(S) if s.get('dirk') == 'После брони'), None)
cta = next(q for q, s in enumerate(S) if s.get('kind') == 'cta')
if k is not None:
    s = S.pop(k)
    s['note'] = re.sub(r'\[дожим · блок \d+:[^\]]*\]', '[дожим · блок 1: Гарантия первого клиента]', s.get('note') or '')
    s['note'] += '  Ставится сразу за кнопкой: до неё дублировал «что фиксирует десятка», после — работает как ответ тем, кто уже нажал.'
    S.insert(cta + 1, s)
    print('✅ «После брони» переставлен в блок 1, сразу за кнопкой')

# 2. номер блока в dirk
NAMES = {1:'Гарантия',2:'Не один',3:'Не ещё одна информация',4:'Команда агентов',5:'Вопрос клиентов',
         6:'Охотник в подарок',7:'Я не особенный',8:'Дизайн',9:'Сценарий А/Б',10:'Видео',
         11:'Половина окупит',12:'Реклама',13:'Три набора',14:'Продавцы',15:'Рассрочка',
         16:'Аватар',17:'Под ключ',18:'Визуализация',19:'Ниши и страны',20:'Кейсы',21:'Финал и Q&A'}
n = 0
for s in S:
    if s.get('a') != 1: continue
    b = blk(s)
    if not b: continue
    dk = re.sub(r'^Д\d+ · ', '', s.get('dirk') or '')
    dk = re.sub(r'^(Гарантия|Дизайн и креативы|Продающие AI-видео|Реклама агентами|AI-продавцы|Контент и AI-аватар|Рассрочка)$', r'\1', dk)
    s['dirk'] = f'Б{b} · {dk}'
    n += 1
print(f'✅ номер блока проставлен в dirk на {n} слайдах дожима')

seq, order = [], []
for k, s in enumerate(S, 1):
    if s.get('a') != 1: continue
    b = blk(s)
    if b and (not order or order[-1] != b): order.append(b)
print('\nпорядок блоков:', ' → '.join(map(str, order)))
broken = [(order[q-1], order[q]) for q in range(1, len(order)) if order[q] < order[q-1]]
print('нарушений последовательности:', broken or 'нет')
print('пропущено номеров:', sorted(set(range(1,22)) - set(order)) or 'нет')
if not APPLY: print('\nпредпросмотр. Запись — с флагом --apply'); sys.exit(0)
stamp = datetime.datetime.now().strftime('%d%m-%H%M')
shutil.copy(V6, V6.with_name(f'PREZA-EFIRA-v6.pered-nomerami-{stamp}.html'))
V6.write_text(src[:i + len('var S = ')] + json.dumps(S, ensure_ascii=False, indent=1) + src[j + 2:], encoding='utf-8')
print(f'\nзаписано. бэкап → PREZA-EFIRA-v6.pered-nomerami-{stamp}.html')
