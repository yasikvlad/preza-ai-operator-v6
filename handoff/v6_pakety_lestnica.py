# -*- coding: utf-8 -*-
"""v6: оформление наборов — возвращаем лестницу и поднимаем карточки.

Что не так было. В v6 пакетный блок это три почти одинаковые финансовые таблицы плюс две
тройки карточек, где единственная крупная цифра — цена. Слайда, на котором разницу наборов
видно за секунду, не осталось: лестница «Агенты по наборам» (ступени Bronze–Silver–Gold,
чипы агентов, счётчик 1 → 4 → 7) в v6 не попала, хотя вся её вёрстка лежит в шапке файла.

Что делаем:
1. Возвращаем лестницу первым слайдом пакетного блока — без плашки «мой выбор»
   (снята в пачке 9) и без потолка дохода (тоже снят). Добавляем вторую цифру роста:
   агентов на $600 / $2.200 / $5.200 — по стеку из Элемента 2.
2. Карточки «Три набора» и «Витрина цен» перестают висеть в верхней трети экрана:
   модификатор .tall тянет их на высоту слайда, цифры становятся соразмерны цене.

Запуск: python3 handoff/v6_pakety_lestnica.py [--apply]
"""
import json, shutil, sys, datetime, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, 'PREZA-EFIRA-v6.html')
APPLY = '--apply' in sys.argv

src = open(F, encoding='utf-8').read()
i = src.index('var S = [')
j = src.index('\n];', i)
S = json.loads(src[i + len('var S = '):j + 2])

def find(dirk):
    for n, s in enumerate(S):
        if s.get('dirk') == dirk:
            return n
    sys.exit(f'нет слайда {dirk}')

def ach(icon, name, new=False, star=False, d=0.35):
    cls = 'ach' + (' new' if new else '') + (' star' if star else '')
    return f"<span class=\"{cls}\" style=\"--d:{d}s\"><i>{icon}</i>{name}</span>"

BRONZE = [ach('🌐', 'AI-сайты', new=True, d=.35)]
SILVER = [ach('🌐', 'AI-сайты', d=.35), ach('🎨', 'AI-дизайн', new=True, d=.45),
          ach('🎬', 'AI-видео', new=True, d=.55), ach('✍️', 'Контент-завод', new=True, d=.65)]
GOLD = [ach('🌐', 'AI-сайты', d=.35), ach('🎨', 'AI-дизайн', d=.45), ach('🎬', 'AI-видео', d=.55),
        ach('✍️', 'Контент-завод', d=.65), ach('🎯', 'AI-таргет', new=True, d=.75),
        ach('🧭', 'AI-SEO', new=True, d=.85), ach('💬', 'AI-продавец', new=True, d=.95),
        ach('⭐', 'страт-сессии', new=True, star=True, d=1.15)]

def step(name, sub, chips, cnt, word, money, i, lead=False):
    return (f"<div class=\"step{' lead' if lead else ''}\" style=\"--i:{i}\">"
            f"<div class=\"st-h\"><b>{name}</b><small>{sub}</small></div>"
            f"<div class=\"achips\">{''.join(chips)}</div>"
            f"<div class=\"st-n\"><div><b class=\"cnt\" data-to=\"{cnt}\">{cnt}</b><small>{word}</small></div>"
            f"<div><b>{money}</b><small>агентов на</small></div></div></div>")

LESTNICA = {
    'a': 0, 'lv': 9, 'mvp': 1, 't': '',
    'b': ("<div class='tl2'><div class=\"stack-v\">"
          "<div class=\"eyebrow\">Агенты по наборам</div>"
          "<h2 class=\"dh md\">Чем наборы отличаются: какие агенты у вас работают</h2>"
          "<div class=\"stairs\">"
          + step('Bronze', 'делаете сами', BRONZE, 1, 'агент', '$600', 0)
          + step('Silver', 'контент приводит клиентов', SILVER, 4, 'агента', '$2.200', 1, lead=True)
          + step('Gold', 'продаёт и удерживает агент', GOLD, 7, 'агентов', '$5.200', 2)
          + "</div>"
          "<p class=\"note center\">Закрашенный агент — новый в этом наборе. Ничего не исчезает — только прибавляется</p>"
          "</div></div>"),
    'dirk': 'Агенты по наборам',
    'note': ('единственный слайд блока, где разницу наборов видно за секунду и без чтения. '
             'Идти слева направо: «Bronze — один агент, сайты. Silver — плюс дизайн, видео и '
             'контент-завод. Gold — плюс реклама, видимость и продавец». Дать чипам догореть, '
             'потолок дохода не называть — он снят со слайдов наборов. ~25 сек.'),
    'disc': 1,
}

pos = find('Набор Gold')
if not any(s.get('dirk') == 'Агенты по наборам' for s in S):
    S.insert(pos, LESTNICA)
    print(f'  ✓ лестница «Агенты по наборам» вставлена первым слайдом пакетного блока (#{pos + 1})')
else:
    print('  · лестница уже есть')

# ── карточки наборов на всю высоту слайда ──────────────────────────────────────
for dirk in ('Три набора', 'Витрина цен'):
    n = find(dirk)
    b = S[n]['b']
    if 'plans tall' in b or 'plans trio tall' in b:
        print(f'  · {dirk}: уже поднято')
        continue
    S[n]['b'] = b.replace('class="plans trio"', 'class="plans trio tall"').replace(
        'class="plans"', 'class="plans tall"')
    print(f'  ✓ {dirk}: карточки на высоту слайда')

CSS = """
/* наборы: карточки тянутся на высоту слайда, а не висят в верхней трети.
   .tall — модификатор к существующему .plans, чтобы не трогать другие тройки в деке */
.tl2 .plans.tall .plan{min-height:46cqh;display:flex;flex-direction:column;justify-content:center;gap:1.1cqh}
.tl2 .plans.tall .plan-n{font-size:4cqw}
.tl2 .plans.tall .now{font-size:6.4cqw}
.tl2 .plans.tall .was{font-size:2.5cqw}
.tl2 .plans.tall .plan-d{font-size:2.15cqw}
.tl2 .plans.trio.tall .pspec{margin-top:1.4cqh}
.tl2 .plans.trio.tall .prow b{font-size:2.6cqw}
.tl2 .plans.trio.tall .prow span{font-size:1.8cqw}
"""

if '.plans.tall' not in src:
    m = re.search(r'\n\s*</style>', src)
    src = src[:m.start()] + '\n' + CSS + src[m.start():]
    i = src.index('var S = [')
    j = src.index('\n];', i)

out = src[:i + len('var S = ')] + json.dumps(S, ensure_ascii=False, indent=1) + src[j + 2:]
print(f'слайдов стало {len(S)}')

if APPLY:
    stamp = datetime.datetime.now().strftime('%d%m-%H%M')
    shutil.copy(F, os.path.join(ROOT, f'PREZA-EFIRA-v6.pered-lestnicey-{stamp}.html'))
    tmp = F + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(out)
    os.replace(tmp, F)
    print('записано')
else:
    print('предпросмотр. записать: --apply')
