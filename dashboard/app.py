"""볼트 체결 검사 앱 (스키마 v1.1)

실행:  streamlit run dashboard/app.py
왼쪽 메뉴: 검사 현황(전체 이력) / 타음 검사(소리) / 비전 검사(사진).
"""
import streamlit as st

st.set_page_config(page_title="볼트 체결 검사", page_icon="🔩", layout="wide")
nav = st.navigation([
    st.Page("home.py", title="검사 현황", icon="📊", default=True),
    st.Page("tapping.py", title="타음 검사", icon="🔨"),
    st.Page("vision.py", title="비전 검사", icon="📷"),
])
nav.run()
