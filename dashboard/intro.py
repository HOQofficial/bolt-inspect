"""소개 페이지 (시안 D) — 주소 창에 처음 들어왔을 때 보이는 밝은 소개 화면. web/landing.html 을 그대로 보여 줌."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

HERE = Path(__file__).resolve().parent
src = next((p for p in (HERE / "landing.html", HERE.parent / "web" / "landing.html") if p.exists()), None)

st.markdown("""<style>
[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="collapsedControl"], .st-key-topbar, .rs-fixed { display:none !important; }
[data-testid="stMainBlockContainer"], .block-container { padding:0 !important; max-width:100% !important; }
[data-testid="stMain"] { overflow:hidden !important; }
[data-testid="stElementContainer"] { margin:0; }
.rs-ribw { display:none !important; }
[data-testid="stElementContainer"]:not(:has(iframe)) { display:none !important; }
[data-testid="stVerticalBlock"] { gap:0 !important; }
iframe { border:0; display:block; width:100% !important; height:100vh !important; min-height:600px; }
</style>""", unsafe_allow_html=True)

if src is None:
    st.error("소개 페이지 파일(web/landing.html)을 찾지 못했어요. 왼쪽 메뉴 대신 주소 끝에 /home 을 붙여 들어가세요.")
    st.stop()

html = src.read_text(encoding="utf-8")
# 소개 페이지 안의 버튼을 이 대시보드의 화면으로 연결 (안쪽 틀을 벗어나 전체 화면에서 열기)
def _go(path):
    # 틀(iframe) 안에서는 주소를 직접 바꿀 수 없어서, 바깥 Streamlit 화면의 이동 기능을 대신 불러 줌
    return (f'href="{path}" onclick="try{{var P=window.parent;P.history.pushState({{}},\'\',\'{path}\');'
            f'P.dispatchEvent(new P.PopStateEvent(\'popstate\',{{state:{{}}}}));}}catch(e){{window.open(\'{path}\',\'_blank\');}}return false;"')


html = (html.replace('href="app/?tab=history"', _go("/home"))
            .replace('href="app/"', _go("/tapping"))
            .replace('href="app/icons/icon-192.png"', 'href="data:,"'))
if hasattr(st, "iframe"):                     # 새 Streamlit
    st.iframe(html, height=1000)
else:                                          # 예전 Streamlit
    components.html(html, height=1000, scrolling=True)
