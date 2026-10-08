"""화면 공용 부품: 큰 판정 배너, 상태 배지, 게이지, 스펙트럼."""
import plotly.graph_objects as go
import streamlit as st

# 밝은/어두운 테마 모두에서 읽히는 진한 색 + 흰 글씨
# 폰 앱(web/app/style.css)과 같은 색: 주황 포인트 + 초록(정상) / 노랑(재측정) / 빨강(이상)
ACCENT = "#ff5900"
COLOR = {"OK": "#1f9d55", "CHECK": "#e6b800", "NG": "#e0413a", None: "#64748b"}
SOFT = {"OK": "#e4f5ea", "CHECK": "#fff7cf", "NG": "#fde8e6", None: "#f1f5f9"}
GRAD = {"OK": "linear-gradient(135deg,#1f9d55,#3fc27a)", "CHECK": "linear-gradient(135deg,#ffd93d,#ffec8a)",
        "NG": "linear-gradient(135deg,#e0413a,#f37a70)", None: "linear-gradient(135deg,#64748b,#94a3b8)"}
ON_GRAD = {"OK": "#fff", "CHECK": "#4a3b00", "NG": "#fff", None: "#fff"}
BAND = "#cfe8d9"          # 정상 범위 칸 (연한 세이지 그린)
KO = {"OK": "정상", "CHECK": "재측정 필요", "NG": "체결 이상 의심", None: "미검사"}
KO_SHORT = {"OK": "정상", "CHECK": "재측정", "NG": "이상"}
ICON = {"OK": "●", "CHECK": "▲", "NG": "■", None: "○"}


def banner(title, result, sub=""):
    """화면 맨 위 큰 판정 표시 (조원 V3 의 종합 판정을 크게)"""
    st.markdown(
        f"""<div style="background:{GRAD[result]};color:{ON_GRAD[result]};border-radius:22px;padding:22px 28px;margin:6px 0 14px">
        <div style="font-size:15px;opacity:.9">{title}</div>
        <div style="font-size:38px;font-weight:600;line-height:1.25">{ICON[result]} {KO[result]}</div>
        <div style="font-size:14px;opacity:.9">{sub}</div></div>""",
        unsafe_allow_html=True)


def tile(title, result, lines):
    """플랜지 카드: 왼쪽 색 띠 + 큰 판정 글자"""
    body = "<br>".join(lines)
    st.markdown(
        f"""<div style="border:1px solid rgba(128,128,128,.35);border-left:8px solid {COLOR[result]};
        border-radius:16px;padding:12px 16px;margin-bottom:12px">
        <div style="font-size:14px;opacity:.75">{title}</div>
        <div style="font-size:22px;font-weight:600;color:{COLOR[result]}">{ICON[result]} {KO[result]}</div>
        <div style="font-size:13px;opacity:.8;margin-top:4px">{body}</div></div>""",
        unsafe_allow_html=True)


def badge_style(v):
    """표 셀 색칠 (OK/CHECK/NG 또는 한글 판정)"""
    rev = {k_: k for k, k_ in KO.items()} | {k_: k for k, k_ in KO_SHORT.items()}
    r = v if v in COLOR else rev.get(v)
    return f"background-color:{SOFT[r]};color:#111;font-weight:600" if r else ""


def gauge(title, val, lo, hi, suffix="", fmt=".2f"):
    """기준 범위(초록) 안에 값(파란 막대)이 있는지 보여주는 막대 게이지 (조원 V3)
    축은 기준 범위와 '측정값'이 모두 들어오게 잡고, 색 칸은 축 안으로 잘라서 상자 밖으로 안 튀어나오게 함."""
    span = max(hi - lo, 1e-9)
    pad = .65 * span
    xmin, xmax = lo - pad, hi + pad
    margin = .1 * max(xmax - xmin, 1e-9)
    xmin, xmax = min(xmin, val - margin), max(xmax, val + margin)   # 측정값이 범위 밖이어도 축 안에 보이게
    xmin = max(0, xmin)                                              # 특징값은 모두 0 이상
    if suffix.strip() == "%":
        xmax = min(xmax, 100)                                        # 에너지 비율은 100% 까지
    lo_c, hi_c = max(lo, xmin), min(hi, xmax)                        # 초록 칸도 축 안으로
    inside = lo <= val <= hi
    steps = [{"range": r, "color": c} for r, c in (([xmin, lo_c], "#eef0f4"), ([lo_c, hi_c], BAND),
                                                   ([hi_c, xmax], "#eef0f4")) if r[1] > r[0]]
    f = go.Figure(go.Indicator(
        mode="number+gauge", value=val, domain={"x": [0.32, 1], "y": [0, 1]},
        number={"suffix": suffix, "valueformat": fmt, "font": {"size": 24, "color": COLOR["OK"] if inside else COLOR["NG"]}},
        title={"text": ("✓ " if inside else "✕ ") + title, "font": {"size": 13,
               "color": COLOR["OK"] if inside else COLOR["NG"]}},
        gauge={"shape": "bullet", "axis": {"range": [xmin, xmax]}, "bar": {"color": "#ffb48a", "thickness": .35},
               "steps": steps, "threshold": {"line": {"color": ACCENT, "width": 4}, "thickness": .8, "value": val}}))
    f.update_layout(height=90, margin=dict(l=10, r=10, t=10, b=20))
    return f


def spectrum_bars(trace, peak_hz, band, label):
    """ESP32 가 보낸 FFT 막대(trace = {f_max, v:[0~100...]})를 그림. 초록 칸 = 정상 Peak 주파수 범위(band), 점선 = 이번 Peak.
    폰·태블릿 화면의 FFT 그래프와 같은 모양."""
    n, fmax = len(trace["v"]), trace["f_max"]
    x = [fmax * (i + .5) / n for i in range(n)]
    f = go.Figure(go.Scatter(x=x, y=trace["v"], mode="lines", fill="tozeroy", fillcolor="rgba(255,89,0,.10)", line={"color": ACCENT, "width": 1.8}))
    if band and band[1] > 0:
        f.add_vrect(x0=band[0], x1=max(band[1], band[0] + fmax / 400), fillcolor=BAND, opacity=.9, line_width=0, layer="below")
    f.add_vline(x=peak_hz, line_color=ACCENT, line_width=1.5, annotation_text=label, annotation_font_color="#6b7587")
    f.update_layout(height=260, margin=dict(l=20, r=20, t=30, b=20), showlegend=False,
                    xaxis={"title": "Frequency (Hz)", "range": [0, fmax]}, yaxis={"title": "Magnitude (0~100)", "range": [0, 105]})
    return f


def next_click(title, step, done, total):
    """비전 페이지: 다음에 클릭할 곳 안내 카드"""
    st.markdown(
        f"""<div style="border:2px dashed #ff5900;border-radius:12px;padding:14px 18px;margin-bottom:10px">
        <div style="font-size:13px;opacity:.75">{title} · {done}/{total}</div>
        <div style="font-size:24px;font-weight:700;color:#ff5900">{step}</div></div>""",
        unsafe_allow_html=True)
