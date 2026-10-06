"""검사 현황 - 플랜지별 상태를 한눈에, 이력과 엑셀 성적서."""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

import store
import ui
from schema_rules import KST, RESULT_RANK, worst


ss = st.session_state


def load(full=False):
    """처음에만 전체를 읽고, 그다음부터는 '새로 생긴 기록'만 읽어 합침 (Firebase 읽기 한도 절약).
    미래 날짜로 찍힌 시험 기록이 있어도 새 기록을 놓치지 않도록 '지금까지의 가장 최근 시각'을 기준으로 함."""
    now_iso = datetime.now(KST).isoformat(timespec="seconds")
    if full or "insp_db" not in ss:
        ss.insp_db = {d["record_id"]: d for d in store.list_inspections()}
        ss.flanges_db, ss.flanges_at = store.list_flanges(), datetime.now(KST)
    else:
        past = [d["inspected_at"] for d in ss.insp_db.values() if d["inspected_at"] <= now_iso]
        for d in store.inspections_since(max(past) if past else "0"):
            ss.insp_db[d["record_id"]] = d
        if (datetime.now(KST) - ss.flanges_at).total_seconds() > 300:        # 플랜지 정보는 5분마다만
            ss.flanges_db, ss.flanges_at = store.list_flanges(), datetime.now(KST)
    return list(ss.insp_db.values()), ss.flanges_db


st.title("볼트 체결 검사 현황")
ca, cb = st.columns([2, 1])
auto = ca.toggle("자동 새로고침 (태블릿 앱에서 저장한 기록이 저절로 보여요)", value=True,
                 help="켜 두면 아래 간격마다 새 기록을 다시 읽어요. Firebase 는 읽은 문서 수만큼 무료 한도(하루 5만 건)를 쓰므로, "
                      "기록이 많을 땐 간격을 길게 하거나 쓰지 않을 땐 끄세요.")
if cb.button("🔄 전체 다시 읽기", help="모든 기록을 처음부터 다시 읽어요 (기록이 많으면 읽기 한도를 많이 써요)"):
    ss.pop("insp_db", None)
every = cb.selectbox("간격", [10, 30, 60], index=1, format_func=lambda s: f"{s}초마다", disabled=not auto,
                     label_visibility="collapsed")


def page():
    insp, flanges = load()
    st.caption(f"데이터: {store.source_name()} · 마지막으로 읽은 시각 {datetime.now(KST):%H:%M:%S}"
               + (f" · {every}초마다 자동 새로고침" if auto else " · 자동 새로고침 꺼짐 (F5 로 새로고침)"))
    if not insp:
        st.info("아직 검사 기록이 없습니다. 왼쪽 '타음 검사'에서 측정해 보세요.")
        return

    df = pd.json_normalize(insp)
    df["inspected_at"] = pd.to_datetime(df["inspected_at"], utc=True).dt.tz_convert("Asia/Seoul")
    fl_info = {f["flange_id"]: f for f in flanges}

    # 볼트(및 GAP)별 현재 상태 = 가장 최근 검사.
    # 단, 타음과 비전을 따로 저장했을 수 있으므로 '최근 타음 판정'과 '최근 비전 판정' 중 더 나쁜 쪽을 씀.
    srt = df.sort_values("inspected_at")
    latest = srt.groupby(["flange_id", "bolt_id"]).tail(1).copy()
    # v1.2: 비전은 '돌출'과 'I-마킹'을 따로 저장할 수 있으므로 각각의 최근 판정을 봄
    if "vision.result" in srt and "vision.protrusion_mm" in srt:
        srt["_prot"] = srt["vision.result"].where(srt["vision.protrusion_mm"].notna())
    if "vision.marking.result" in srt:
        srt["_mark"] = srt["vision.marking.result"]
    TRACKS = ("tapping.result", "_prot", "_mark")
    for col in TRACKS:
        if col in srt:
            last = srt.dropna(subset=[col]).groupby(["flange_id", "bolt_id"])[col].last()
            latest[col + ".last"] = [last.get((a, b)) for a, b in zip(latest.flange_id, latest.bolt_id)]
    _s = lambda v: v if isinstance(v, str) else None   # 빈칸(NaN) -> None
    latest["final_result"] = [
        worst(r.final_result, *(_s(r.get(c + ".last")) for c in TRACKS)) if r.type == "BOLT"
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
                "tapping.score": "범위 이탈 수", "vision.protrusion_mm": "돌출(mm)", "vision.marking.gap_pct": "마킹 끊김(%)",
                "gap.gap_diff_mm": "틈 편차(mm)"}
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


st.fragment(page, run_every=f"{every}s" if auto else None)()
