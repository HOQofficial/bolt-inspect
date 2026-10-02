"""화면 공용 부품: 큰 판정 배너, 상태 배지, 게이지, 스펙트럼."""
import plotly.graph_objects as go
import streamlit as st

# 밝은/어두운 테마 모두에서 읽히는 진한 색 + 흰 글씨
COLOR = {"OK": "#15803d", "CHECK": "#b45309", "NG": "#b91c1c", None: "#64748b"}
SOFT = {"OK": "#dcfce7", "CHECK": "#fef3c7", "NG": "#fee2e2", None: "#f1f5f9"}
KO = {"OK": "정상", "CHECK": "재측정 필요", "NG": "체결 이상 의심", None: "미검사"}
KO_SHORT = {"OK": "정상", "CHECK": "재측정", "NG": "이상"}
ICON = {"OK": "●", "CHECK": "▲", "NG": "■", None: "○"}


def banner(title, result, sub=""):
    """화면 맨 위 큰 판정 표시 (조원 V3 의 종합 판정을 크게)"""
    st.markdown(
        f"""<div style="background:{COLOR[result]};color:#fff;border-radius:14px;padding:22px 28px;margin:6px 0 14px">
        <div style="font-size:15px;opacity:.9">{title}</div>
        <div style="font-size:40px;font-weight:700;line-height:1.25">{ICON[result]} {KO[result]}</div>
        <div style="font-size:14px;opacity:.9">{sub}</div></div>""",
        unsafe_allow_html=True)


def tile(title, result, lines):
    """플랜지 카드: 왼쪽 색 띠 + 큰 판정 글자"""
    body = "<br>".join(lines)
    st.markdown(
        f"""<div style="border:1px solid rgba(128,128,128,.35);border-left:8px solid {COLOR[result]};
        border-radius:10px;padding:12px 16px;margin-bottom:12px">
        <div style="font-size:14px;opacity:.75">{title}</div>
        <div style="font-size:24px;font-weight:700;color:{COLOR[result]}">{ICON[result]} {KO[result]}</div>
        <div style="font-size:13px;opacity:.8;margin-top:4px">{body}</div></div>""",
        unsafe_allow_html=True)


def badge_style(v):
    """표 셀 색칠 (OK/CHECK/NG 또는 한글 판정)"""
    rev = {k_: k for k, k_ in KO.items()} | {k_: k for k, k_ in KO_SHORT.items()}
    r = v if v in COLOR else rev.get(v)
    return f"background-color:{SOFT[r]};color:#111;font-weight:600" if r else ""


def gauge(title, val, lo, hi, suffix="", fmt=".2f"):
    """기준 범위(초록) 안에 값(파란 막대)이 있는지 보여주는 막대 게이지 (조원 V3)"""
    span = max(hi - lo, 1e-9)
    pad = .65 * span
    xmin, xmax = max(0, lo - pad), hi + pad
    inside = lo <= val <= hi
    f = go.Figure(go.Indicator(
        mode="number+gauge", value=val, domain={"x": [0.32, 1], "y": [0, 1]},
        number={"suffix": suffix, "valueformat": fmt, "font": {"size": 26, "color": COLOR["OK"] if inside else COLOR["NG"]}},
        title={"text": ("✓ " if inside else "✕ ") + title, "font": {"size": 13,
               "color": COLOR["OK"] if inside else COLOR["NG"]}},
        gauge={"shape": "bullet", "axis": {"range": [xmin, xmax]}, "bar": {"color": "#2563eb"},
               "steps": [{"range": [xmin, lo], "color": "#f1f5f9"},
                         {"range": [lo, hi], "color": "#bbf7d0"},
                         {"range": [hi, xmax], "color": "#f1f5f9"}],
               "threshold": {"line": {"color": "#111827", "width": 3}, "value": val}}))
    f.update_layout(height=90, margin=dict(l=10, r=10, t=10, b=20))
    return f


def spectrum(x, y, peak, label):
    f = go.Figure(go.Scatter(x=x, y=y, mode="lines", line={"color": "#2563eb"}))
    f.add_vline(x=peak, line_dash="dash", annotation_text=label)
    f.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20),
                    xaxis_title="Frequency (Hz)", yaxis_title="Magnitude", showlegend=False)
    return f


def next_click(title, step, done, total):
    """비전 페이지: 다음에 클릭할 곳 안내 카드"""
    st.markdown(
        f"""<div style="border:2px dashed #2563eb;border-radius:12px;padding:14px 18px;margin-bottom:10px">
        <div style="font-size:13px;opacity:.75">{title} · {done}/{total}</div>
        <div style="font-size:24px;font-weight:700;color:#2563eb">{step}</div></div>""",
        unsafe_allow_html=True)
