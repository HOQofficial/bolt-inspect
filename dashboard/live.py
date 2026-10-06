"""실시간 보기: 폰·태블릿 앱이 방금 저장한 타음 측정을 PC 화면에 그대로 보여줌.

폰이 블루투스로 받아 판정하고 Firebase 에 저장 → 이 화면이 몇 초마다 '가장 최근 기록 1건'을 읽어 같은 모양으로 그림.
(PC 는 블루투스를 받지 않고 저장된 기록만 읽어요. key.json 이 있어야 폰 기록이 보여요.)
"""
import pandas as pd
import streamlit as st

import store
import ui
from schema_rules import ACC_DEFAULT_REF, FEATURE_KO, RESULT_KO  # noqa: F401

st.title("실시간 보기 (폰·태블릿)")
top = st.columns([3, 1])
every = top[0].selectbox("새로 읽는 간격", [2, 3, 5, 10], index=1, format_func=lambda s: f"{s}초마다",
                         help="가장 최근 기록 몇 건만 읽어서 읽기 한도는 거의 안 써요 (1번에 8건).")
auto = top[1].toggle("자동 새로고침", value=True)

SNAME = {"mic": "음향", "acc": "진동"}
FMT = {"peak_hz": (" Hz", ".0f"), "mag": ("", ".3f"), "energy_pct": (" %", ".1f")}
UNIT = {"mic": {"peak_hz": "Hz", "mag": "0~1", "energy_pct": "%"},
        "acc": {"peak_hz": "Hz", "mag": "g", "energy_pct": "%"}}


def fmt_of(s, k):
    return (" g", ".3f") if (s, k) == ("acc", "mag") else FMT[k]


def label(s, k):
    return f"{FEATURE_KO[k]} ({UNIT[s][k]})"


@st.cache_data(ttl=60)
def flange_ref(fid):
    f = next((x for x in store.list_flanges() if x["flange_id"] == fid), None)
    return (f or {}).get("tap_ref")


def page():
    try:
        recs = store.latest_inspections(8)
    except Exception as e:
        st.error(f"기록을 읽지 못했어요: {e}")
        return
    st.caption(f"데이터: {store.source_name()} · 마지막으로 읽은 시각 {pd.Timestamp.now(tz='Asia/Seoul'):%H:%M:%S}")
    if not recs:
        st.info("아직 저장된 기록이 없어요. 폰 앱에서 측정하면 여기에 나타나요.")
        return
    r = recs[0]
    tp = r.get("tapping")
    when = pd.to_datetime(r["inspected_at"]).strftime("%m/%d %H:%M:%S")
    c = st.columns(4)
    c[0].metric("검사 대상", f"{r['flange_id']}-{r['bolt_id']}")
    c[1].metric("검사자", r.get("inspector", "-"))
    c[2].metric("기기", r.get("device_id", "-"))
    c[3].metric("측정 시각", when)
    ui.banner(f"{r['flange_id']}-{r['bolt_id']} 종합 판정", r["final_result"],
              (f"범위를 벗어난 특징값 {tp['score']}개 · 기준: {tp.get('ref_source', '-')}" if tp else "타음 값 없음"))
    if not tp or tp.get("model") != "range" or not tp.get("features"):
        st.caption("이 기록은 특징값이 없는 형식이라 게이지를 그리지 못해요.")
    else:
        ref = dict(flange_ref(r["flange_id"]) or {})
        if not ref.get("acc"):
            ref["acc"] = ACC_DEFAULT_REF     # 앱·타음 화면과 같은 임시 기본 범위
        cols = st.columns(2)
        for col, s in zip(cols, ("mic", "acc")):
            with col:
                name = "🎤 음향 · INMP441" if s == "mic" else "📳 진동 · MPU6050"
                feats, res = tp["features"].get(s), (tp.get("sensor_results") or {}).get(s)
                if feats is None:
                    st.info(f"{name} · 이번 측정에 {SNAME[s]} 값이 오지 않았어요")
                    continue
                checks = (tp.get("checks") or {}).get(s) or {}
                ui.tile(name, res, [" &nbsp;|&nbsp; ".join(
                    f"{label(s, k)} {'✓' if checks.get(k) else '✕'}" for k in ("peak_hz", "mag", "energy_pct"))])
                rr = ref.get(s)
                if not rr:
                    continue
                for k in ("peak_hz", "mag", "energy_pct"):
                    st.plotly_chart(ui.gauge(label(s, k), feats[k], rr[k][0], rr[k][1], *fmt_of(s, k)),
                                    width="stretch", key=f"lg_{s}_{k}")
        st.caption("게이지의 초록 범위는 이 플랜지에 지금 저장된 기준이에요. 판정과 ✓/✕ 는 폰이 측정할 때 계산한 값 그대로예요.")
    st.subheader("최근 기록")
    rows = [{"시간": pd.to_datetime(d["inspected_at"]).strftime("%m/%d %H:%M:%S"),
             "대상": f"{d['flange_id']}-{d['bolt_id']}", "검사자": d.get("inspector", "-"),
             "판정": ui.KO[d["final_result"]],
             "음향 Peak(Hz)": (((d.get("tapping") or {}).get("features") or {}).get("mic") or {}).get("peak_hz"),
             "진동 Peak(Hz)": (((d.get("tapping") or {}).get("features") or {}).get("acc") or {}).get("peak_hz"),
             "기기": d.get("device_id", "-")} for d in recs]
    t = pd.DataFrame(rows)
    st.dataframe(t.style.map(ui.badge_style, subset=["판정"]).format(
        {"음향 Peak(Hz)": "{:.1f}", "진동 Peak(Hz)": "{:.1f}"}, na_rep="-"), hide_index=True, width="stretch")


st.fragment(page, run_every=f"{every}s" if auto else None)()
