# -*- coding: utf-8 -*-
"""v6 · акт 8: структура — добор айсберга, переносы в дожим, сливы, перестановка наборов.

Порядок акта 8 после скрипта (по ТЗ: переход → что входит → стек и цена → дефицит → кнопка):
  айсберг → два пути → предложение → доступ-не-курс → как устроено → не кнопка
  → блоки 1–5 программы → стек 17 элементов → дефицит
  → леджеры Gold→Silver→Bronze → сравнение → if-all → анкор → два пути автора
  → карточки Bronze→Silver→Gold → состав Gold → РЕАЛЬНАЯ ЦЕНА → цена эфира → арифметика
  → бронь → что фиксирует → путь оплаты → не набор, а решение → КНОПКА
"""
import json, shutil, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
V6   = ROOT / 'PREZA-EFIRA-v6.html'
V4   = ROOT / 'PREZA-EFIRA-v4.html'
APPLY = '--apply' in sys.argv

def load(p):
    s = p.read_text(encoding='utf-8')
    i, j = s.index('var S = ['), s.index('\n];', s.index('var S = ['))
    return s, i, j, json.loads(s[i + len('var S = '):j + 2])

src, i, j, S = load(V6)
_, _, _, S4 = load(V4)

def by_dirk(arr, d):
    return next((k for k, x in enumerate(arr) if x.get('dirk') == d), None)

log = []

# ── 1. добираем айсберг из v4: это и есть «переход от секрета 3» по ТЗ ───────
if by_dirk(S, 'Айсберг') is None:
    ice = json.loads(json.dumps(S4[by_dirk(S4, 'Айсберг')]))
    ice['a'] = 0
    S.insert(0, ice)
    log.append('айсберг добран из v4 первым слайдом — это «переход от секрета 3» по ТЗ')

# ── 2. в дожим: слайды, у которых по ТЗ свой блок после кнопки ──────────────
CTA = by_dirk(S, 'CTA 1')
TO_DOZHIM = [
    ('Внутри агента',        'дожим 4 · как работает команда агентов'),
    ('Умеете после блока 2', 'дожим 18 · визуализация, развернуть в 6 экранов'),
    ('Блок 2 в цифрах',      'дожим 18 · вслед за серией умений'),
    ('Агенты блока 3',       'дожим 8/10/16 · разбить на дизайн, видео, контент-завод'),
    ('Агенты блока 4',       'дожим 12 · разбить на таргет, SEO, охотник'),
    ('Агент блока 5',        'дожим 14 · AI-продавцы, живая демонстрация'),
    ('А что после',          'дожим 3 · это не ещё одна информация'),
    ('Кому подходит',        'дожим · к блоку возражений перед Q&A'),
    ('Эти деньги и так уйдут', 'дожим 15 · парой со слайдом рассрочки'),
    ('После брони',          'дожим 1 · сразу за кнопкой'),
]
moved = []
for d, why in TO_DOZHIM:
    k = by_dirk(S, d)
    if k is None or k > CTA: continue
    s = S.pop(k)
    s['a'] = 1
    s.setdefault('st', ['edit', 'перенесён в дожим по ТЗ'])
    moved.append((s, why))
    CTA = by_dirk(S, 'CTA 1')
# ставим переносы сразу после кнопки, в порядке списка
for n, (s, why) in enumerate(moved):
    s['note'] = (s.get('note') or '') + f'  [{why}]'
    S.insert(CTA + 1 + n, s)
log.append(f'в дожим перенесено: {len(moved)} слайдов')

# ── 3. сливы ────────────────────────────────────────────────────────────────
def merge(dst_dirk, src_dirk, note):
    a, b = by_dirk(S, dst_dirk), by_dirk(S, src_dirk)
    if a is None or b is None: return False
    S[a]['note'] = (S[a].get('note') or '') + '  ' + note
    S.pop(b)
    return True

if merge('Как устроено', 'Инструкция и задание',
         'Скрин воркшопа — пруфом прямо на этом слайде, отдельного экрана нет.'):
    log.append('«Инструкция и задание» слита в «Как устроено»')
if merge('Три набора', 'Агенты по наборам',
         'Сетка «услуги / агенты / модули / недели» — здесь же, отдельного экрана нет.'):
    log.append('«Агенты по наборам» слита в «Три набора»')
if merge('Почему не сам', 'Почему не сам · зачем мне это',
         'Второй абзац: «И честно — физически я все деньги не заработаю».'):
    log.append('«зачем мне это» слита в «Почему не сам»')

# ── 4. снять совсем ─────────────────────────────────────────────────────────
for d, why in [('Живые Q&A', 'повторяет стек, элемент 7'),
               ('Первый клиент', 'два if-all подряд — дубль приёма, остаётся «If-all 3»')]:
    k = by_dirk(S, d)
    if k is not None:
        S.pop(k); log.append(f'снят «{d}» — {why}')

# ── 5. перестановка ценового блока ──────────────────────────────────────────
def take(d):
    k = by_dirk(S, d)
    return S.pop(k) if k is not None else None

order = ['Почему не когда угодно', 'Набор Gold', 'Набор Silver', 'Набор Bronze', 'Три набора',
         'If-all 3', 'Анкоринг', 'Два пути автора', 'Почему не сам',
         'Bronze: описание', 'Silver: описание', 'Gold: описание', 'Стек целиком',
         'Витрина цен', 'Главная арифметика']
block = [x for x in (take(d) for d in order) if x]
anchor = by_dirk(S, 'Элемент 17')
if anchor is None: anchor = by_dirk(S, 'Бронь 10') - 1
for n, s in enumerate(block):
    S.insert(anchor + 1 + n, s)
log.append('ценовой блок пересобран: дефицит → Gold→Silver→Bronze → сравнение → if-all → анкор → '
           'два пути автора → карточки Bronze→Silver→Gold → состав Gold → цена эфира → арифметика')

for k, s in enumerate(S):
    s['a'] = 0 if k <= by_dirk(S, 'CTA 1') else 1

cta = by_dirk(S, 'CTA 1') + 1
print('\n'.join('· ' + l for l in log))
print(f'\nv6: {len(S)} слайдов · акт 8 — {cta} · дожим — {len(S) - cta}')
if not APPLY:
    print('\nпредпросмотр. Запись — с флагом --apply'); sys.exit(0)

stamp = datetime.datetime.now().strftime('%d%m-%H%M')
shutil.copy(V6, V6.with_name(f'PREZA-EFIRA-v6.pered-strukturoy-{stamp}.html'))
V6.write_text(src[:i + len('var S = ')] + json.dumps(S, ensure_ascii=False, indent=1) + src[j + 2:], encoding='utf-8')
print(f'записано. бэкап → PREZA-EFIRA-v6.pered-strukturoy-{stamp}.html')
