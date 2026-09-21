#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт деки в PPTX так, чтобы слайд выглядел ровно как в браузере И текст остался редактируемым.

Как это работает. Старый export-pptx.py перерисовывал слайд с нуля по разобранному тексту —
поэтому вся вёрстка (лестницы, леджеры, таблицы, панели, доски) в PPTX не попадала.
Здесь наоборот:

  1. Playwright открывает деку и по очереди показывает каждый слайд.
  2. Каждый текстовый узел оборачивается в <span> и прячется через visibility:hidden —
     разметка при этом не двигается, а псевдоэлементы, рамки, фоны и картинки остаются на месте.
  3. Снимок квадратного холста без текста уходит в слайд подложкой — это «плита».
  4. Поверх плиты кладутся настоящие текстовые блоки PPTX на тех же координатах,
     с размером, цветом, начертанием и выравниванием из браузера.

Итог: картинка точная, а любую надпись можно править прямо в PowerPoint или Keynote.

Запуск:
  ~/.claude/skills/editorial-carousel/.venv/bin/python3 export-pptx-vizual.py            # вся дека
  ... export-pptx-vizual.py --from 269 --to 375                                          # только часть
  ... export-pptx-vizual.py --out /путь/файл.pptx --px 1400 --quality 72
"""
import asyncio, json, os, re, sys, tempfile, shutil, math
# Playwright стоит в venv скилла editorial-carousel, python-pptx — в системном python3.
# Поэтому скрипт умеет две фазы: --shoot снимает кадры, --build собирает файл.
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
except ImportError:
    Presentation = None

HERE = os.path.dirname(os.path.abspath(__file__))

def arg(name, default=None, cast=str):
    if name in sys.argv:
        return cast(sys.argv[sys.argv.index(name) + 1])
    return default

# какую деку снимаем: по умолчанию мастер, через --deck можно v6
DECK_NAME = arg('--deck', 'PREZA-EFIRA-v4.html')
DECK = os.path.join(HERE, DECK_NAME)
URL  = 'http://localhost:4173/' + DECK_NAME
OUT     = arg('--out', os.path.join(HERE, 'PREZA-EFIRA-v4-vizual.pptx'))
PX      = arg('--px', 1400, int)          # сторона квадратного холста в пикселях
QUALITY = arg('--quality', 72, int)       # качество jpeg подложки
FROM    = arg('--from', 1, int)
WAIT    = arg('--wait', 2100, int)        # мс на доигрывание анимаций перед снимком
FREEZE = '--no-freeze' not in sys.argv   # видео на паузе: быстрее и детерминированнее
TO      = arg('--to', 0, int)

SIDE = 9144000                             # квадрат 10×10 дюймов в EMU
PT_PER_PX = 720.0 / PX                     # 10 дюймов = 720 pt

# семейства из CSS → шрифты, которые реально стоят в системе
FAM = {'f-display': 'Unbounded', 'f-mono': 'Menlo', 'f-body': 'Manrope'}
def pick_font(css_family):
    f = (css_family or '').split(',')[0].strip().strip('"\'')
    if not f or f.startswith('var('):
        return FAM['f-body']
    low = f.lower()
    if 'mono' in low or 'menlo' in low or 'courier' in low: return FAM['f-mono']
    return f

ALIGN_NAMES = {'center': 'CENTER', 'right': 'RIGHT', 'end': 'RIGHT',
               'justify': 'JUSTIFY', 'left': 'LEFT', 'start': 'LEFT'}

# ─────────────────────────────────────────── браузерная часть

PREP_JS = r"""
() => {
  document.body.classList.remove('draft');
  // чистый режим: прячет слоты «📎 ОБЯЗАТЕЛЬНО» и «🖼 ВИЗУАЛ» — это пометки
  // монтажёрам, в файле для клиента и на экране эфира им не место
  document.body.classList.add('clean');
  if (!document.getElementById('_pptx_style')) {
    const st = document.createElement('style');
    st.id = '_pptx_style';
    // служебная обвязка веб-деки: метка акта, счётчик слайдов, полоса прогресса,
    // плавающая кнопка брони и бейдж пометки. В файле для клиента им не место.
    st.textContent = '._pptxt{visibility:hidden!important}'
      + '#ctaOverlay,#hud,#act,#bar,#stcount,.stbadge{display:none!important}';
    document.head.appendChild(st);
  }
  return true;
}
"""

# обёртка делается уже после того, как счётчики досчитали, — иначе countUps
# перезаписывает textContent и сносит span, а цифра остаётся видимой в подложке
WRAP_JS = r"""
() => {
  const sl = document.querySelector('#stage .slide.on');
  if (!sl) return 0;
  const SKIP = new Set(['SCRIPT','STYLE','TITLE','NOSCRIPT','TEXTAREA']);
  const w = document.createTreeWalker(sl, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let n; while (n = w.nextNode()) {
    const txt = n.textContent.trim();
    if (!txt) continue;
    // узлы без букв и цифр — это эмодзи, стрелки, галочки. Их метрики в PowerPoint
    // отличаются от браузерных, и текстовый блок наезжает на соседей.
    // Оставляем их прямо в подложке: выглядит точно, редактировать там нечего.
    if (!/[0-9A-Za-zА-Яа-яЁё]/.test(txt)) continue;
    const pe = n.parentElement;
    if (!pe || SKIP.has(pe.tagName) || pe.classList.contains('_pptxt')) continue;
    nodes.push(n);
  }
  for (const nd of nodes) {
    // не <span>: в деке `.frow span`, `.r99 span`, `.ch span` — стиль мелкой подписи,
    // и обёрнутая цифра 40px превращалась в 18px. Свой элемент CSS не трогает.
    const sp = document.createElement('pptx-t');
    sp.className = '_pptxt';
    nd.parentNode.replaceChild(sp, nd);
    sp.appendChild(nd);
  }
  return nodes.length;
}
"""

RUNS_JS = r"""
() => {
  const stage = document.getElementById('stage');
  const sl = stage.querySelector('.slide.on');
  if (!sl) return {w: 0, h: 0, runs: []};
  const r0 = stage.getBoundingClientRect();
  // .tl2 масштабируется трансформом — кегль надо умножить на тот же масштаб
  const scaleOf = (el) => {
    let s = 1, p = el;
    while (p && p !== stage) {
      const tr = getComputedStyle(p).transform;
      if (tr && tr !== 'none') { try { s *= new DOMMatrixReadOnly(tr).a; } catch (e) {} }
      p = p.parentElement;
    }
    return s;
  };
  const out = [];
  // Куски одного абзаца (текст + <em> + текст) в PowerPoint должны стать одним
  // блоком с несколькими ранами: коробка на каждый кусок ломается на переносе —
  // кусок, начавшийся в середине строки и ушедший на следующую, ложится поверх первого.
  const ids = new Map(); let nid = 0;
  const idOf = el => { if (!ids.has(el)) ids.set(el, ++nid); return ids.get(el); };
  const blockOf = el => { let b = el; while (b && b !== stage && getComputedStyle(b).display.startsWith('inline')) b = b.parentElement; return b || el; };
  // <br> внутри абзаца: следующий кусок начинает новую строку
  const brBefore = new Set(); { let pend = null;
    sl.querySelectorAll('._pptxt, br').forEach(n => {
      const b = blockOf(n.parentElement || n);
      if (n.tagName === 'BR') pend = b; else { if (pend && pend === b) brBefore.add(n); pend = null; } }); }
  sl.querySelectorAll('._pptxt').forEach(sp => {
    const t = sp.textContent.replace(/\s+/g, ' ').trim();
    if (!t) return;
    const rect = sp.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    if (rect.bottom < r0.top || rect.top > r0.bottom) return;
    const host = sp.parentElement || sp;
    const cs = getComputedStyle(host);
    if (cs.visibility === 'collapse' || cs.display === 'none') return;
    const sc = scaleOf(host);
    // Ширину блока, а не чернил. getBoundingClientRect у многострочного span —
    // это габарит самой длинной строки. Если делать коробку по нему, PowerPoint
    // со своими метриками переносит иначе, строк становится больше, и блок
    // наезжает на соседний. Берём контентную ширину ближайшего блочного предка:
    // именно она задаёт перенос в браузере.
    const blk = blockOf(host);
    const br = blk.getBoundingClientRect();
    const bs = getComputedStyle(blk);
    const padL = parseFloat(bs.paddingLeft) || 0, padR = parseFloat(bs.paddingRight) || 0;
    out.push({
      t,
      blk: idOf(blk), br: brBefore.has(sp),
      sb: /^\s/.test(sp.textContent), sa: /\s$/.test(sp.textContent),
      x: rect.left - r0.left, y: rect.top - r0.top, w: rect.width, h: rect.height,
      cx: br.left - r0.left + padL, cw: Math.max(br.width - padL - padR, 1),
      size: parseFloat(cs.fontSize) * sc,
      weight: parseInt(cs.fontWeight) || 400,
      color: cs.color,
      align: cs.textAlign,
      family: cs.fontFamily,
      tt: cs.textTransform,
      ls: (parseFloat(cs.letterSpacing) || 0) * sc,
      italic: cs.fontStyle === 'italic',
      strike: (cs.textDecorationLine || '').includes('line-through'),
      lines: Math.max(1, sp.getClientRects().length),   // сколько строк заняло в браузере
      lh: parseFloat(cs.lineHeight) || 0,               // шаг строки в px (0 = normal)
      // Прозрачность накопительная: opacity родителя не наследуется в computed style,
      // поэтому текст внутри скрытой карточки (.vbeat без .on) читался как видимый
      // и все восемь глав стоп-скролла ложились друг на друга.
      opacity: (() => { let o = 1, e = host;
        while (e && e !== stage) { const s = getComputedStyle(e);
          if (s.visibility === 'hidden' || s.display === 'none') return 0;
          o *= parseFloat(s.opacity) || 0; e = e.parentElement; }
        return o; })()
    });
  });
  return {w: r0.width, h: r0.height, runs: out};
}
"""

async def grab(shots_dir, lo, hi):
    data = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={'width': PX, 'height': PX}, device_scale_factor=1)
        await pg.goto(URL, wait_until='load', timeout=60000)
        await pg.wait_for_timeout(1800)
        total = await pg.evaluate("() => S.length")
        hi = hi or total
        await pg.evaluate(PREP_JS)
        print(f'дека: {total} слайдов')
        stage = await pg.query_selector('#stage')
        for n in range(lo, hi + 1):
            await pg.evaluate("(i) => show(i)", n - 1)
            if FREEZE:
                # видео душат headless-браузер декодированием: ставим осмысленный
                # кадр и замораживаем. Для статичной плиты этого достаточно.
                await pg.evaluate("""() => document.querySelectorAll('.slide.on video')
                    .forEach(v => { try { v.pause(); if (v.readyState > 1 && v.currentTime < .4)
                        v.currentTime = Math.min(12, (v.duration || 3) * 0.4); } catch(e){} })""")
            await pg.wait_for_timeout(WAIT)         # дать анимациям и счётчикам доиграть
            await pg.evaluate(WRAP_JS)              # и только потом оборачивать текст
            info = await pg.evaluate(RUNS_JS)
            path = os.path.join(shots_dir, f'{n:04d}.jpg')
            await stage.screenshot(path=path, type='jpeg', quality=QUALITY)
            note = await pg.evaluate("(i) => (S[i] && S[i].note) || ''", n - 1)
            # У видеослайда на подложку попадает только текущая глава — остальные
            # прозрачны. Чтобы в PPTX не потерялись, складываем их в заметки.
            beats = await pg.evaluate(
                "(i) => ((S[i] && S[i].beats) || []).map(b => (S[i].kind==='scroll' ? Math.round(b[0]*100)+'% · ' : b[0]+'с · ') "
                "+ b[1].replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim()).join('\\n')", n - 1)
            if beats: note = (note + '\n\nГлавы ролика:\n' + beats).strip()
            dirk = await pg.evaluate("(i) => (S[i] && S[i].dirk) || ''", n - 1)
            data.append({'n': n, 'img': path, 'runs': info['runs'], 'note': note, 'dirk': dirk})
            if n % 25 == 0 or n == hi:
                print(f'  снято {n - lo + 1}/{hi - lo + 1}')
        await b.close()
    return data

# ─────────────────────────────────────────── сборка pptx


def place(r):
    """Где и какой ширины ставить блок. Запас добавляется со стороны, куда текст растёт:
       при выравнивании влево — только справа, при центровке — симметрично, вправо — только слева.
       Иначе блок уезжает на величину запаса."""
    align = (r.get('align') or 'left').split()[0]
    multiline = (r.get('lines') or 0) > 1 if r.get('lines') else r['h'] > r['size'] * 1.9
    if multiline and r.get('cw'):
        # переносим по той же колонке, что и браузер — тогда число строк совпадёт
        w = max(min(r['cw'], float(PX)), 12)
        x = min(max(0.0, r['cx']), float(PX) - w)
        return x, w, align, True
    pad = max(r['w'] * (0.06 if multiline else 0.18), 6)
    w = r['w'] + pad * 2
    if align == 'center':
        x = r['x'] - pad
    elif align in ('right', 'end'):
        x = r['x'] - pad * 2
    else:
        x = r['x']
    # блок не должен вылезать за холст: сначала ужимаем ширину, потом двигаем внутрь,
    # у центрованных сохраняем середину, чтобы текст не съехал вбок
    w = max(min(w, float(PX)), 12)
    if align == 'center':
        c = r['x'] + r['w'] / 2
        x = c - w / 2
    x = min(max(0.0, x), float(PX) - w)
    return x, w, align, multiline

# ─────────────────────────────────────────── подгонка кегля
# Браузер переносит заголовок по своим метрикам, PowerPoint / Keynote / Quick Look — по своим:
# другой кернинг, псевдожирный у переменных шрифтов, округление кегля до 0,1 pt. Заголовок
# «Откуда берётся первый клиент…» влезал в колонку с запасом 5 px из 1176 — и в PPTX
# уходил на третью строку поверх подзаголовка. Поэтому каждый блок промеряется теми же
# ttf, что стоят в системе, с запасом по ширине; не влезает в число строк браузера —
# кегль ужимается шагами по 2,5 %, шаг строки при этом не меняется, и блок сохраняет высоту.
FONT_FILES = {
    'Unbounded': '/Users/vladyasko/Library/Fonts/Unbounded.ttf',
    'Manrope':   '/Users/vladyasko/Library/Fonts/Manrope.ttf',
    'Menlo':     '/System/Library/Fonts/Menlo.ttc',
}
WEIGHT_NAMES = [(900, 'Black'), (800, 'ExtraBold'), (700, 'Bold'), (600, 'SemiBold'),
                (500, 'Medium'), (400, 'Regular'), (300, 'Light'), (200, 'ExtraLight')]
HEADROOM_BOLD, HEADROOM = 0.06, 0.04     # запас ширины: жирным больше — псевдожирный шире
FLOOR = 0.70                             # ниже 70 % кегля не ужимаем, дальше это уже другой слайд
_fonts, _measure = {}, [None]

def font_for(family, weight, px):
    from PIL import ImageFont
    name = pick_font(family)
    path = FONT_FILES.get(name) or FONT_FILES['Manrope']
    key = (path, int(weight), int(round(px)))
    if key in _fonts: return _fonts[key]
    try:
        if name == 'Menlo':
            f = ImageFont.truetype(path, max(4, int(round(px))), index=1 if weight >= 600 else 0)
        else:
            f = ImageFont.truetype(path, max(4, int(round(px))))
            names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
            want = next((nm for wt, nm in WEIGHT_NAMES if wt <= weight and nm in names), None) \
                   or next((nm for wt, nm in reversed(WEIGHT_NAMES) if nm in names), None)
            if want: f.set_variation_by_name(want)
    except Exception:
        f = ImageFont.load_default()
    _fonts[key] = f
    return f

def _dr():
    if _measure[0] is None:
        from PIL import Image, ImageDraw
        _measure[0] = ImageDraw.Draw(Image.new('L', (8, 8)))
    return _measure[0]

def text_w(f, txt, ls=0.0):
    w = _dr().textlength(txt, font=f)
    if ls > 0: w += ls * max(0, len(txt) - 1)     # положительный трекинг PowerPoint честно добавит
    return w

def greedy_lines(f, txt, W, ls=0.0):
    lines = []
    for para in txt.split('\n'):        # \n — принудительный перенос (<br>)
        cur = ''
        for word in para.split(' '):
            probe = (cur + ' ' + word).strip()
            if cur and text_w(f, probe, ls) > W:
                lines.append(cur); cur = word
            else:
                cur = probe
        lines.append(cur)
    return lines

def run_text(r):
    txt = r['t']
    if r.get('tt') == 'uppercase': return txt.upper()
    if r.get('tt') == 'lowercase': return txt.lower()
    return txt

def join_text(rs):
    out, prev = '', None
    for r in rs:
        if prev is not None:
            out += '\n' if r.get('br') else (' ' if (prev.get('sa') or r.get('sb')) else '')
        out += run_text(r); prev = r
    return out

def items(rec):
    """Видимые раны слайда, сгруппированные по блоку: куски одного абзаца — одна коробка."""
    groups, order = {}, []
    for r in rec['runs']:
        if r.get('opacity', 1) < 0.06: continue      # скрытое анимацией — на слайде его нет
        key = r.get('blk') or ('solo', id(r))
        if key not in groups: groups[key] = []; order.append(key)
        groups[key].append(r)
    out = []
    for key in order:
        rs = groups[key]
        if len(rs) == 1:
            b = dict(rs[0]); b['runs'] = rs; out.append(b); continue
        y0 = min(r['y'] for r in rs); y1 = max(r['y'] + r['h'] for r in rs)
        x0 = min(r['x'] for r in rs); x1 = max(r['x'] + r['w'] for r in rs)
        big = max(rs, key=lambda r: r['size'])          # стиль коробки — от самого крупного куска
        pitch = big.get('lh') or 0
        if pitch < big['size'] * 0.85: pitch = big['size'] * 1.25
        b = dict(big)
        b.update({'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0, 'runs': rs, 't': join_text(rs), 'tt': 'none',
                  'lines': max(1, round((y1 - y0) / pitch)), 'weight': max(r.get('weight', 400) for r in rs)})
        out.append(b)
    return out

def layout(r):
    """Координаты + кегль, при котором текст гарантированно ляжет в те же строки, что в браузере."""
    x, w, align, multiline = place(r)
    txt, weight, ls0 = run_text(r), r.get('weight', 400), r.get('ls', 0) or 0
    L = max(1, int(r.get('lines') or 1)) if r.get('lines') else (
        max(1, round(r['h'] / (r.get('lh') or r['size'] * 1.25))) if multiline else 1)
    W = w * (1 - (HEADROOM_BOLD if weight >= 600 else HEADROOM))
    size, floor = float(r['size']), float(r['size']) * FLOOR
    while True:
        f = font_for(r.get('family'), weight, size)
        ls = ls0 * size / r['size']
        need = len(greedy_lines(f, txt, W, ls)) if multiline else (2 if text_w(f, txt, ls) > W else 1)
        if need <= L or size * 0.975 < floor: break
        size *= 0.975
    lh = r.get('lh') or 0
    pitch = lh if lh >= r['size'] * 0.85 else (r['h'] / L if L > 1 else r['h'])
    return {'x': x, 'w': w, 'align': align, 'multiline': multiline, 'size': size,
            'lines': L, 'pitch': pitch, 'fits': need <= L,
            'shrink': 1 - size / r['size'], 'font': f, 'text': txt, 'ls': ls}

def rgb(css):
    m = re.match(r'rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)', css or '')
    if not m: return RGBColor(0xE8, 0xEF, 0xEA)
    return RGBColor(int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3))))

def fmt_run(run, r, scale=1.0):
    f = run.font
    f.size = Pt(max(5.0, round(r['size'] * scale * PT_PER_PX, 1)))
    f.bold = r.get('weight', 400) >= 600
    f.italic = bool(r.get('italic'))
    f.name = pick_font(r.get('family'))
    f.color.rgb = rgb(r.get('color'))
    rpr = run._r.get_or_add_rPr()
    if r.get('ls'):
        rpr.set('spc', str(int(round(r['ls'] * scale * PT_PER_PX * 100))))
    if r.get('strike'):
        rpr.set('strike', 'sngStrike')
    # латиница и кириллица одним шрифтом
    for tag in ('a:latin', 'a:cs', 'a:ea'):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {}); rpr.append(el)
        el.set('typeface', pick_font(r.get('family')))

def put_text(sl, r):
    lay = layout(r)
    x, w, align, multiline = lay['x'], lay['w'], lay['align'], lay['multiline']
    width = Emu(int(w * PT_PER_PX * 12700))
    height = Emu(int(max(r['h'] + 4, lay['lines'] * lay['pitch'] + 4, 10) * PT_PER_PX * 12700))
    left = Emu(int(x * PT_PER_PX * 12700))
    top = Emu(int(r['y'] * PT_PER_PX * 12700))
    tb = sl.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = bool(multiline)
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    # выключаем автоподгон: координаты уже посчитаны
    bp = tf._txBody.find(qn('a:bodyPr'))
    if bp is not None:
        el = bp.find(qn('a:spAutoFit'))
        if el is not None: bp.remove(el)
        if bp.find(qn('a:normAutofit')) is None:   # пусть PowerPoint ужмёт, если не влезло
            bp.append(bp.makeelement(qn('a:normAutofit'), {}))
    p = tf.paragraphs[0]
    p.alignment = getattr(PP_ALIGN, ALIGN_NAMES.get(align, 'LEFT'))
    if multiline:   # шаг строки точно как в браузере — иначе рендерер ставит свой и блок растёт
        p.line_spacing = Pt(round(lay['pitch'] * PT_PER_PX, 1))
    scale = lay['size'] / r['size'] if r.get('size') else 1.0   # ужатие кегля — на все куски абзаца
    def para_style(pp):
        pp.alignment = getattr(PP_ALIGN, ALIGN_NAMES.get(align, 'LEFT'))
        if multiline: pp.line_spacing = Pt(round(lay['pitch'] * PT_PER_PX, 1))
    prev = None
    for piece in (r.get('runs') or [r]):
        if piece.get('br') and prev is not None:
            p = tf.add_paragraph(); para_style(p); prev = None
        txt = run_text(piece)
        if prev is not None and (prev.get('sa') or piece.get('sb')): txt = ' ' + txt
        run = p.add_run(); run.text = txt
        fmt_run(run, piece, scale)
        prev = piece


# ─────────────────────────────────────────── предпросмотр раскладки
# Рисует слайд так же, как его соберёт PowerPoint: та же подложка, та же функция place().
# Нужен, чтобы поймать сдвиги ДО отправки файла — по картинке видно сразу.
def preview(data, num, out_png):
    from PIL import Image, ImageDraw
    rec = next(d for d in data if d['n'] == num)
    im = Image.open(rec['img']).convert('RGB'); dr = ImageDraw.Draw(im)
    for r in items(rec):
        lay = layout(r); f = lay['font']; w, align = lay['w'], lay['align']
        lines = greedy_lines(f, lay['text'], w, lay['ls']) if lay['multiline'] else [lay['text']]
        pitch = lay['pitch'] if lay['multiline'] else r['h']
        for k, line in enumerate(lines):
            tw = text_w(f, line, lay['ls'])
            if align == 'center':   tx = lay['x'] + (w - tw) / 2
            elif align in ('right', 'end'): tx = lay['x'] + w - tw
            else:                   tx = lay['x']
            dr.text((tx, r['y'] + k * pitch + (pitch - lay['size'] * 1.15) / 2), line, font=f, fill=rgb_tuple(r.get('color')))
        dr.rectangle([lay['x'], r['y'], lay['x'] + w, r['y'] + max(r['h'], len(lines) * pitch)],
                     outline=(255, 176, 46) if lay['shrink'] else (60, 60, 60), width=1)
    im.save(out_png)
    return out_png

def rgb_tuple(css):
    c = rgb(css); return (c[0], c[1], c[2])

# ─────────────────────────────────────────── проверка раскладки
# Прогон без PowerPoint: какие блоки пришлось ужать, какие не влезли даже на полу,
# и где после подгонки блок всё равно наезжает на соседа или уходит за холст.
def check(data):
    bad = 0
    for d in data:
        boxes, notes = [], []
        for r in items(d):
            lay = layout(r)
            hgt = lay['lines'] * lay['pitch'] if lay['multiline'] else r['h']
            boxes.append((lay['x'], r['y'], lay['x'] + lay['w'], r['y'] + hgt, r, lay))
            tag = lay['text'][:48] + ('…' if len(lay['text']) > 48 else '')
            if not lay['fits']:
                notes.append(f'    ✖ не влезает даже при −{lay["shrink"]*100:.0f} %: «{tag}»'); bad += 1
            elif lay['shrink'] > 0:
                notes.append(f'    ↓ кегль −{lay["shrink"]*100:.0f} % ({r["size"]:.0f}→{lay["size"]:.0f}px): «{tag}»')
            if r['y'] + hgt > PX + 2:
                notes.append(f'    ✖ уходит за низ холста: «{tag}»'); bad += 1
        # новые наложения: в браузере блоки не пересекались, а после переноса — да
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                (x0, y0, x1, y1, ra, la), (u0, v0, u1, v1, rb, lb) = boxes[i], boxes[j]
                ox = min(x1, u1) - max(x0, u0); oy = min(y1, v1) - max(y0, v0)
                if ox <= 2 or oy <= 2: continue
                by = min(ra['y'] + ra['h'], rb['y'] + rb['h']) - max(ra['y'], rb['y'])
                if by > 2: continue          # пересекались и в браузере — так задумано
                notes.append(f'    ✖ наезд: «{la["text"][:30]}» ↔ «{lb["text"][:30]}»'); bad += 1
        if notes:
            print(f'#{d["n"]} · {d.get("dirk") or ""}'); print('\n'.join(notes))
    print(f'\nпроблемных мест: {bad}' if bad else '\nвсё влезает, наездов нет')
    return bad

def build(data, out):
    prs = Presentation()
    prs.slide_width = SIDE; prs.slide_height = SIDE
    blank = prs.slide_layouts[6]
    for d in data:
        sl = prs.slides.add_slide(blank)
        sl.shapes.add_picture(d['img'], 0, 0, width=SIDE, height=SIDE)
        for r in items(d):
            put_text(sl, r)
        if d['note']:
            sl.notes_slide.notes_text_frame.text = f"{d['dirk']}\n\n{d['note']}"
    prs.save(out)
    return out

def main():
    work = arg('--work', os.path.join(tempfile.gettempdir(), 'pptx-vizual'))
    if '--shoot' in sys.argv:
        assert async_playwright, 'нет playwright: запусти venv скилла editorial-carousel'
        os.makedirs(work, exist_ok=True)
        data = asyncio.run(grab(work, FROM, TO))
        with open(os.path.join(work, 'runs.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        print(f'кадры и текст в {work}')
        return
    if '--preview' in sys.argv:
        assert Presentation, 'нужен системный python3 (для rgb/place достаточно, но держим один вход)'
        with open(os.path.join(work, 'runs.json'), encoding='utf-8') as f:
            data = json.load(f)
        n = arg('--preview', 0, int)
        out = preview(data, n, f'/tmp/preview-{n}.png')
        print('предпросмотр раскладки:', out)
        return
    if '--check' in sys.argv:
        with open(os.path.join(work, 'runs.json'), encoding='utf-8') as f:
            data = json.load(f)
        check(data)
        return
    if '--build' in sys.argv:
        assert Presentation, 'нет python-pptx: запусти системным python3'
        with open(os.path.join(work, 'runs.json'), encoding='utf-8') as f:
            data = json.load(f)
        print('собираю pptx…')
        build(data, OUT)
        mb = os.path.getsize(OUT) / 1024 / 1024
        boxes = sum(len(d['runs']) for d in data)
        print(f'готово: {OUT}\n  слайдов {len(data)} · текстовых блоков {boxes} · {mb:.1f} МБ')
        return
    print(__doc__)

if __name__ == '__main__':
    main()
