"""검사 현황 - 플랜지별 상태를 한눈에, 이력과 엑셀 성적서."""
import io

import pandas as pd
import streamlit as st

import store
import ui
from schema_rules import RESULT_RANK, worst


@st.cache_data(ttl=15)
def load():
    return store.list_inspections(), store.list_flanges()


insp, flanges = load()
st.title("볼트 체결 검사 현황")
st.caption(f"데이터: {store.source_name()} · 15초마다 새로 읽음")
if not insp:
    st.info("아직 검사 기록이 없습니다. 왼쪽 '타음 검사'에서 측정해 보세요.")
    st.stop()

df = pd.json_normalize(insp)
df["inspected_at"] = pd.to_datetime(df["inspected_at"], utc=True).dt.tz_convert("Asia/Seoul")
fl_info = {f["flange_id"]: f for f in flanges}

# 볼트(및 GAP)별 현재 상태 = 가장 최근 검사.
# 단, 타음과 비전을 따로 저장했을 수 있으므로 '최근 타음 판정'과 '최근 비전 판정' 중 더 나쁜 쪽을 씀.
srt = df.sort_values("inspected_at")
latest = srt.groupby(["flange_id", "bolt_id"]).tail(1).copy()
for col in ("tapping.result", "vision.result"):
    if col in srt:
        last = srt.dropna(subset=[col]).groupby(["flange_id", "bolt_id"])[col].last()
        latest[col + ".last"] = [last.get((a, b)) for a, b in zip(latest.flange_id, latest.bolt_id)]
_s = lambda v: v if isinstance(v, str) else None   # 빈칸(NaN) -> None
latest["final_result"] = [
    worst(r.final_result, _s(r.get("tapping.result.last")), _s(r.get("vision.result.last"))) if r.type == "BOLT"
    else r.final_result for _, r in latest.iterrows()]

# ---- 1. 전체 상태 배너 ----
cnt = latest.final_result.value_counts()
overall = worst(*latest.final_result.tolist())
ui.banner("전체 상태 (볼트별 최신 검사 기준)", overall,
          f"이상 {cnt.get('NG', 0)} · 재측정 {cnt.get('CHECK', 0)} · 정상 {cnt.get('OK', 0)}  |  "
          f"플랜지 {latest.flange_id.nunique()}개, 마지막 검사 {df.inspected_at.max():%m/%d %H:%M}")

k1, k2, k3, k4 = st.columns(4)
k1.metric("전체 검사 기록", len(df))
k2.metric("검사한 볼트(현재)", int((latest.type == "BOLT").sum()))
k3.metric("재측정 필요", int(cnt.get("CHECK", 0)))
k4.metric("체결 이상 의심", int(cnt.get("NG", 0)))

# ---- 2. 플랜지 카드 (나쁜 순서) ----
st.subheader("플랜지별 상태")
cards = []
for fid, g in latest.groupby("flange_id"):
    bolts = g[g.type == "BOLT"]
    gap = g[g.type == "GAP"]
    res = worst(*g.final_result.tolist())
    f = fl_info.get(fid, {})
    lines = [f"{f.get('zone', '-')} · {f.get('bolt_spec', '')} × {f.get('bolt_count', '')}",
             f"볼트 {len(bolts)}개: 이상 {(bolts.final_result == 'NG').sum()} · 재측정 {(bolts.final_result == 'CHECK').sum()}"]
    if not gap.empty and "gap.gap_diff_mm" in gap:
        lines.append(f"틈 편차 {gap['gap.gap_diff_mm'].iloc[0]:.2f} mm")
    lines.append(f"마지막 검사 {g.inspected_at.max():%m/%d %H:%M}")
    cards.append((RESULT_RANK.get(res, -1), fid, res, lines))
cols = st.columns(3)
for i, (_, fid, res, lines) in enumerate(sorted(cards, key=lambda c: (-c[0], c[1]))):
    with cols[i % 3]:
        ui.tile(fid, res, lines)

# ---- 3. 볼트 지도 ----
st.subheader("볼트별 최신 판정")
grid = latest.pivot(index="flange_id", columns="bolt_id", values="final_result").map(lambda v: ui.KO_SHORT.get(v, "") if pd.notna(v) else "")
grid.index.name = "플랜지"
st.dataframe(grid.style.map(ui.badge_style), width="stretch")

# ---- 4. 검사 기록 + 엑셀 ----
st.subheader("검사 기록")
c1, c2 = st.columns(2)
sel_fl = c1.multiselect("플랜지", sorted(df.flange_id.unique()))
sel_res = c2.multiselect("판정", ["정상", "재측정 필요", "체결 이상 의심"])
view = df.copy()
view["판정"] = view.final_result.map(ui.KO)
if sel_fl:
    view = view[view.flange_id.isin(sel_fl)]
if sel_res:
    view = view[view["판정"].isin(sel_res)]
cols_map = {"inspected_at": "검사시각", "flange_id": "플랜지", "bolt_id": "볼트", "inspector": "검사자",
            "판정": "판정", "tapping.features.mic.peak_hz": "음향 Peak(Hz)", "tapping.features.acc.peak_hz": "진동 Peak(Hz)",
            "tapping.score": "범위 이탈 수", "vision.protrusion_mm": "돌출(mm)", "gap.gap_diff_mm": "틈 편차(mm)"}
table = view[[c for c in cols_map if c in view.columns]].rename(columns=cols_map).sort_values("검사시각", ascending=False)
num = {c: "{:.1f}" for c in table.columns if c.endswith(")") and c != "틈 편차(mm)"} | {"틈 편차(mm)": "{:.2f}", "범위 이탈 수": "{:.0f}"}
fmt = {k: v for k, v in num.items() if k in table} | {"검사시각": lambda t: t.strftime("%m/%d %H:%M:%S")}
st.dataframe(table.style.map(ui.badge_style, subset=["판정"]).format(fmt, na_rep="-"), width="stretch", hide_index=True)

buf = io.BytesIO()
out = table.copy()
out["검사시각"] = out["검사시각"].dt.strftime("%Y-%m-%d %H:%M:%S")
out.to_excel(buf, index=False, sheet_name="검사기록")
st.download_button("엑셀 성적서 다운로드", buf.getvalue(), "bolt_inspection_report.xlsx")

# ---- 5. 볼트 이력 ----
st.subheader("볼트 이력")
pick = st.selectbox("플랜지 선택", sorted(df.flange_id.unique()))
hist = df[(df.flange_id == pick) & (df.type == "BOLT")].sort_values("inspected_at")
col = "tapping.features.mic.peak_hz" if "tapping.features.mic.peak_hz" in hist else "tapping.peak_hz"
if not hist.empty and col in hist:
    st.caption("음향 Peak Frequency 추이 (볼트가 풀리면 보통 값이 크게 바뀜)")
    st.line_chart(hist.pivot_table(index="inspected_at", columns="bolt_id", values=col), y_label="Hz")
