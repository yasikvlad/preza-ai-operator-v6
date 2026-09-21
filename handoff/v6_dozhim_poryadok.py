# -*- coding: utf-8 -*-
"""v6 · дожим: расстановка по 21 блоку ТЗ, каркас «контент → кейс → CTA», перенумерация призывов."""
import json, shutil, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
V6 = ROOT / 'PREZA-EFIRA-v6.html'
APPLY = '--apply' in sys.argv
src = V6.read_text(encoding='utf-8')
i, j = src.index('var S = ['), src.index('\n];', src.index('var S = ['))
S = json.loads(src[i + len('var S = '):j + 2])

# блок ТЗ → слайды дожима по dirk, в порядке контент → кейс → CTA
BLOCKS = [
 (1,  'Гарантия первого клиента',            ['Гарантия', 'Кейс Аня', 'CTA 2']),
 (2,  'Вы ни одного дня не один',            ['Не один', 'Кейс Антон']),
 (3,  'Это не ещё одна информация',          ['Не ещё одна информация', 'А что после', 'Кейс Юра', 'CTA 4']),
 (4,  'Как работает команда агентов',        ['Внутри агента']),
 (5,  'Если бы это закрыло вопрос клиентов', ['Окупаемость']),
 (6,  'AI-охотник в подарок',                ['Fast-action у кнопки']),
 (7,  'Я не особенный',                      ['Я не особенный']),
 (8,  'Дизайн и креативы — как создаётся',   ['Агенты блока 3']),
 (9,  'Сценарий А / сценарий Б',             ['Сценарий А', 'Сценарий Б', 'Саша и Наталья', 'CTA 7']),
 (10, 'Продающие AI-видео — как создаётся',  []),
 (11, 'Даже половина окупит вход',           ['Половина результата', 'CTA 8']),
 (12, 'Реклама агентами — как настраивается',['Агенты блока 4']),
 (13, 'Три набора на одном экране',          ['Сравнить наборы', 'Кому подходит']),
 (14, 'AI-продавцы — как продают',           ['Агент блока 5']),
 (15, 'Рассрочка',                           ['Эти деньги и так уйдут', 'После брони']),
 (16, 'Контент и AI-аватар — как создаётся', []),
 (17, 'Под ключ, если есть бизнес',          ['Под ключ', 'Под ключ · что уже поставили']),
 (18, 'Визуализация работы агентов',         ['Умеете после блока 2', 'Блок 2 в цифрах', 'Пять задач']),
 (19, 'Разные ниши, разные страны',          ['С кем работали']),
 (20, 'Кейсы учеников — много кейсов',       ['Кейсы внедрения']),
 (21, 'Финал — ответы на вопросы',           ['Подарки', 'Карта не путешествие', 'CTA 9', 'Легализация QA',
                                              'Экран Q&A · старт', 'Q&A 1', 'Q&A 2', 'Q&A 3', 'Q&A 4', 'Q&A 5',
                                              'Q&A 6', 'Q&A 7', 'Q&A 8', 'Q&A 9', 'Q&A 10', 'Q&A 11',
                                              'Цена ожидания', 'Финал', 'Экран Q&A']),
]

akt8 = [s for s in S if s.get('a') == 0]
pool = {s.get('dirk'): s for s in S if s.get('a') == 1}
used, out, missing = set(), [], []

for num, name, dirks in BLOCKS:
    got = []
    for dk in dirks:
        s = pool.get(dk)
        if s is None: missing.append(f'блок {num} «{name}»: нет «{dk}»'); continue
        s['note'] = (s.get('note') or '') + f'  [дожим · блок {num}: {name}]'
        got.append(s); used.add(dk)
    if not got:
        missing.append(f'блок {num} «{name}»: СОБРАТЬ ЦЕЛИКОМ')
    out += got

lost = [dk for dk in pool if dk not in used]
out += [pool[dk] for dk in lost]

for s in out: s['a'] = 1
S2 = akt8 + out

# перенумерация призывов: в мастере были CTA 1,2,4,7,8,9 — дыры от прошлых версий
n = 0
for s in S2:
    dk = s.get('dirk') or ''
    if dk.startswith('CTA ') or dk == 'Fast-action у кнопки':
        if s.get('kind') == 'cta': continue
        n += 1
        s['dirk'] = f'CTA {n}'
print('\n'.join('⚠️  ' + m for m in missing) if missing else 'все блоки нашли слайды')
if lost: print('\nне разложено по блокам (оставлены в конце):', ', '.join(lost))
print(f'\nv6: {len(S2)} слайдов · акт 8 — {len(akt8)} · дожим — {len(out)} · призывов перенумеровано: {n}')
if not APPLY: print('\nпредпросмотр. Запись — с флагом --apply'); sys.exit(0)
stamp = datetime.datetime.now().strftime('%d%m-%H%M')
shutil.copy(V6, V6.with_name(f'PREZA-EFIRA-v6.pered-dozhimom-{stamp}.html'))
V6.write_text(src[:i + len('var S = ')] + json.dumps(S2, ensure_ascii=False, indent=1) + src[j + 2:], encoding='utf-8')
print(f'записано. бэкап → PREZA-EFIRA-v6.pered-dozhimom-{stamp}.html')
