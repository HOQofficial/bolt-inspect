"""볼트 체결 검사 앱 (스키마 v1.1)

실행:  streamlit run dashboard/app.py
왼쪽 메뉴: 소개(첫 화면) / 검사 현황(전체 이력) / 타음 검사(소리·폰 측정 자동 수신) / 비전 검사(사진).
"""
import streamlit as st

import ui

st.set_page_config(page_title="볼트 체결 검사", page_icon="🔩", layout="wide")
ui.theme_css()                          # 폰 앱과 같은 색·모양 (보기만 바꿈)
import store

P_INTRO = st.Page("intro.py", title="소개", default=True)
P_TAP = st.Page("tapping.py", title="타음 검사", url_path="tapping")
P_HOME = st.Page("home.py", title="검사 현황", url_path="home")
# 비전 검사(vision.py)는 메뉴에서 뺐어요. 파일은 그대로 있고, 다시 쓰려면 아래 줄 주석을 풀고 _pages 에 넣으세요.
# P_VIS = st.Page("vision.py", title="비전 검사", url_path="vision")
_pages = [P_INTRO, P_TAP, P_HOME]
try:
    nav = st.navigation(_pages, position="hidden")   # 메뉴는 아래 시안의 위쪽 바를 씀 (Streamlit 1.46 이상)
except (TypeError, ValueError):
    nav = st.navigation(_pages)                      # 예전 버전은 왼쪽 메뉴를 그대로 사용
ui.ribbon()                                          # 스크롤 따라 내려오는 파란 선 + 위쪽 주황 진행선
ui.topbar(P_TAP, P_HOME, store.KEY.exists(), active=nav.url_path if hasattr(nav, "url_path") else "")
nav.run()
