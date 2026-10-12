from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1440,'height':900})
    pg.goto('http://localhost:8598/'); pg.wait_for_timeout(4000)
    fr=[f for f in pg.frames if f!=pg.main_frame][0]
    n0=fr.evaluate("document.querySelectorAll('svg path').length")
    for i in range(40): pg.mouse.move(300+i*20, 300+(i%5)*12); pg.wait_for_timeout(20)
    print('paths',n0, fr.evaluate("document.querySelectorAll('svg path').length"), fr.evaluate("[...document.querySelectorAll('svg path')].filter(e=>e.getAttribute('d')&&e.getAttribute('d').startsWith('M')).length"))
    fr.click('text=앱 열기'); pg.wait_for_timeout(3000); print(pg.url, pg.locator('text=타음 검사').count())
    b.close()
