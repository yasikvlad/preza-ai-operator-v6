# -*- coding: utf-8 -*-
"""v6 · акт 8: текстовые правки по реестру созвона и дифу презентаций."""
import json, re, shutil, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
V6 = ROOT / 'PREZA-EFIRA-v6.html'
APPLY = '--apply' in sys.argv
src = V6.read_text(encoding='utf-8')
i, j = src.index('var S = ['), src.index('\n];', src.index('var S = ['))
S = json.loads(src[i + len('var S = '):j + 2])
def d(x): return next((k for k, s in enumerate(S) if s.get('dirk') == x), None)

done, miss = [], []
def sub(dirk, old, new, why):
    k = d(dirk)
    if k is None or old not in S[k].get('b', ''): miss.append(f'{dirk}: {why}'); return
    S[k]['b'] = S[k]['b'].replace(old, new, 1); done.append(f'{dirk} — {why}')

# айсберг: цифры в канон
sub('Айсберг', '<li>Больше 96 задач, которые делают агенты</li>',
    '<li>46 готовых задач под ваши услуги</li>', 'снято «96 задач», поставлено каноничное 46')
sub('Айсберг', '<li>21 связка на поиск клиентов</li>',
    '<li>Связки на поиск клиентов под каждую услугу</li>', 'снята необоснованная «21 связка»')

# предложение: 8 задач → 8 агентов, триада ТЗ
sub('AI-Оператор', 'Ваша команда<b>8 задач</b>', 'Ваша команда<b>8 агентов</b>',
    '«8 задач» → «8 агентов»: под плашкой перечислены агенты, а 8 спорило с 16 задачами блока')
sub('AI-Оператор', '<p class="note center">Доступ к системе AI-агентов · инструкция, как ими управлять · навык работы с AI с нуля</p>',
    '<p class="note center"><b>АГЕНТЫ · ИНСТРУКЦИИ · ДОСТУПЫ</b></p>'
    '<p class="note center">Доступ к системе AI-агентов · инструкция, как ими управлять · навык работы с AI с нуля</p>',
    'добавлена триада из ТЗ')

# доступ, а не курс: снять абзац «не продаю уроки»
sub('Доступ, а не курс',
    '<p class="lead">Я не продаю уроки. Я даю доступ к системе, где вы пользуетесь моими агентами — и где мы постоянно разрабатываем новые связки по заработку на них</p>',
    '', 'снят абзац «не продаю уроки» — проговаривается голосом (созвон 03:56)')

# арифметика: один аргумент на цену
sub('Главная арифметика', '<p class="note center">$490 ÷ 30 дней ≈ $16 в день</p>', '',
    'снято «$16 в день» — два расчёта на одну цену гасят друг друга (созвон 18:11)')

# плашка «мой выбор» — снять везде
for dirk in ('Три набора', 'Витрина цен'):
    k = d(dirk)
    if k is None: continue
    b = S[k]['b']
    nb = b.replace('<div class="pill">мой выбор для старта</div>', '').replace(' lead-plan', '')
    if nb != b: S[k]['b'] = nb; done.append(f'{dirk} — снята плашка «мой выбор» (созвон 14:33)')

# витрина цен: двухшаговая лестница
k = d('Витрина цен')
if k is not None:
    b = S[k]['b']
    for was, real in (('$6.060', '$990'), ('$12.390', '$1.490'), ('$21.350', '$2.990')):
        b = b.replace(f'<div class="was">{was}</div>',
                      f'<div class="was">{was}</div><div class="was">{real}</div>', 1)
    b = b.replace('Цена для тех, кто сегодня в эфире', 'Цена для тех, кто сегодня в эфире')
    S[k]['b'] = b
    S[k]['note'] = ('Второй шаг цены: зачёркнуты и ценность, и реальная цена — поверх выходит цена эфира. '
                    'Проговорить: «обычная цена — $990, сегодня для тех, кто в эфире, — $490».')
    done.append('Витрина цен — добавлена вторая зачёркнутая строка $990 / $1.490 / $2.990')

# состав Gold
k = d('Стек целиком')
if k is not None:
    S[k]['b'] = S[k]['b'].replace('<h2 class="dh sm">Что входит целиком</h2>',
                                  '<h2 class="dh sm">Что входит в Gold целиком</h2>', 1)
    done.append('Стек целиком → «Что входит в Gold целиком» (стоит после карточки Gold)')

# сквозняк: сотрудники → задачи
n = 0
for s in S:
    if s.get('a') != 0: continue
    b = s.get('b', '')
    nb = b.replace('сотрудников', 'задач').replace('Сотрудники', 'Задачи')
    if nb != b: s['b'] = nb; n += 1
if n: done.append(f'«сотрудники» → «задачи» на {n} слайдах (пачка 9: считаем задачи)')

print('\n'.join('✅ ' + x for x in done))
if miss: print('\n' + '\n'.join('⚠️  не найдено — ' + x for x in miss))
if not APPLY: print('\nпредпросмотр. Запись — с флагом --apply'); sys.exit(0)
stamp = datetime.datetime.now().strftime('%d%m-%H%M')
shutil.copy(V6, V6.with_name(f'PREZA-EFIRA-v6.pered-tekstom-{stamp}.html'))
V6.write_text(src[:i + len('var S = ')] + json.dumps(S, ensure_ascii=False, indent=1) + src[j + 2:], encoding='utf-8')
print(f'\nзаписано. бэкап → PREZA-EFIRA-v6.pered-tekstom-{stamp}.html')
