# -*- coding: utf-8 -*-
"""Снимки слайдов деки как их видит зал. Запуск:
   python3 audit/snap.py --deck PREZA-EFIRA-v6.html --slides 31,32,33 --out /tmp/snap
   Гонять питоном editorial-carousel (там Playwright)."""
import asyncio, os, sys, subprocess, time
from playwright.async_api import async_playwright

def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
ROOT = os.path.dirname(HERE)
DECK = arg('--deck', 'PREZA-EFIRA-v6.html')
OUT  = arg('--out', '/tmp/snap')
PX   = int(arg('--px', '1080'))
SL   = [int(x) for x in arg('--slides', '1').split(',')]
PORT = int(arg('--port', '4173'))

PREP = r"""() => {
  document.body.classList.remove('draft');
  document.body.classList.add('clean');
  if (!document.getElementById('_snap_style')) {
    const st = document.createElement('style'); st.id='_snap_style';
    st.textContent = '#ctaOverlay,#hud,#act,#bar,#stcount,.stbadge{display:none!important}';
    document.head.appendChild(st);
  } return true; }"""

async def main():
    os.makedirs(OUT, exist_ok=True)
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT)], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    try:
        async with async_playwright() as pw:
            b = await pw.chromium.launch()
            pg = await b.new_page(viewport={'width': PX, 'height': PX}, device_scale_factor=1)
            await pg.goto(f'http://localhost:{PORT}/{DECK}', wait_until='load', timeout=60000)
            await pg.wait_for_timeout(1500)
            await pg.evaluate(PREP)
            st = await pg.query_selector('#stage')
            for n in SL:
                await pg.evaluate('(i) => show(i)', n - 1)
                await pg.wait_for_timeout(2600)
                p = os.path.join(OUT, f'{n:04d}.png')
                await st.screenshot(path=p)
                print(p)
            await b.close()
    finally:
        srv.terminate()

asyncio.run(main())
