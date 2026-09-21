# -*- coding: utf-8 -*-
"""Не вылезает ли содержимое за квадрат слайда. Гонять питоном editorial-carousel.
   python3 audit/perepolnenie.py --deck PREZA-EFIRA-v6.html [--from 1] [--to 125]"""
import asyncio, os, sys, subprocess, time
from playwright.async_api import async_playwright

def arg(n, d=None): return sys.argv[sys.argv.index(n)+1] if n in sys.argv else d
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
DECK=arg('--deck','PREZA-EFIRA-v6.html'); PORT=int(arg('--port','4201'))
LO=int(arg('--from','1')); HI=int(arg('--to','0'))

PREP="""() => {document.body.classList.remove('draft');document.body.classList.add('clean');
 if(!document.getElementById('_ov')){const st=document.createElement('style');st.id='_ov';
 st.textContent='#ctaOverlay,#hud,#act,#bar,#stcount,.stbadge{display:none!important}';
 document.head.appendChild(st);} return true;}"""

MEAS="""() => {const st=document.getElementById('stage');const r=st.getBoundingClientRect();
 let worst=null;
 st.querySelectorAll('.slide.on *').forEach(e=>{
   const b=e.getBoundingClientRect(); if(!b.width||!b.height) return;
   const cs=getComputedStyle(e); if(cs.visibility==='hidden'||cs.display==='none'||parseFloat(cs.opacity)===0) return;
   const over=Math.max(r.top-b.top, b.bottom-r.bottom, r.left-b.left, b.right-r.right);
   if(over>2 && (!worst||over>worst.over)) worst={over:Math.round(over),
     tag:e.tagName.toLowerCase()+'.'+(e.className||'').toString().split(' ').slice(0,2).join('.'),
     txt:(e.textContent||'').trim().slice(0,50)};});
 return worst;}"""

async def main():
    srv=subprocess.Popen([sys.executable,'-m','http.server',str(PORT)],cwd=ROOT,
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1.2)
    bad=0
    try:
        async with async_playwright() as pw:
            b=await pw.chromium.launch()
            pg=await b.new_page(viewport={'width':1080,'height':1080},device_scale_factor=1)
            await pg.goto(f'http://localhost:{PORT}/{DECK}',wait_until='load',timeout=60000)
            await pg.wait_for_timeout(1500); await pg.evaluate(PREP)
            total=await pg.evaluate('() => S.length'); hi=HI or total
            print(f'дека: {total} слайдов, проверяю {LO}–{hi}')
            for n in range(LO,hi+1):
                await pg.evaluate('(i)=>show(i)',n-1); await pg.wait_for_timeout(1700)
                w=await pg.evaluate(MEAS)
                if w:
                    bad+=1
                    d=await pg.evaluate('(i)=>(S[i]&&S[i].dirk)||""',n-1)
                    print(f'  ❌ #{n} [{d}] +{w["over"]}px  {w["tag"]}  «{w["txt"]}»')
            await b.close()
    finally: srv.terminate()
    print('переполнений:', bad)
asyncio.run(main())
