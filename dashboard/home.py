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


ui.page_css()
with st.container(key="refresh"):
    ra, rb, rc_ = st.columns([4, 1.3, 1.3], vertical_alignment="center")
    auto = ra.toggle("자동 새로고침", value=True)
    if rb.button("전체 다시 읽기", help="모든 기록을 처음부터 다시 읽어요 (기록이 많으면 읽기 한도를 많이 써요)", use_container_width=True):
        ss.pop("insp_db", None)
    every = rc_.selectbox("간격", [10, 30, 60], index=1, format_func=lambda s: f"{s}초마다", disabled=not auto,
                          label_visibility="collapsed")


def table_rows(rc, mic_col):
    """검사 기록(DataFrame) -> 시안 표의 행 목록 (최근 측정 기록 · 전체 검사 기록이 같은 모양을 씀)"""
    rows = []
    today = pd.Timestamp.now(tz="Asia/Seoul").date()
    for _, r in rc.iterrows():
        pk = r.get(mic_col) if mic_col in rc else None
        ap = r.get("tapping.features.acc.peak_hz") if "tapping.features.acc.peak_hz" in rc else None
        sc = r.get("tapping.score") if "tapping.score" in rc else None
        tm = f"{r.inspected_at:%H:%M}" if r.inspected_at.date() == today else f"{r.inspected_at:%m/%d %H:%M}"
        rows.append([tm, f"{r.flange_id} · {r.bolt_id}", ui.pill(r.final_result),
                     f"{pk:,.0f} Hz" if pd.notna(pk) else "-", f"{ap:,.0f} Hz" if pd.notna(ap) else "-",
                     f"{int(sc)}개" if pd.notna(sc) else "-"])
    return rows


TABLE_HEAD = ["시간", "플랜지 · 볼트", "판정", "음향", "진동", "벗어남"]


def page():
    insp, flanges = load()
    note = (f"데이터: {store.source_name()} · 마지막으로 읽은 시각 {datetime.now(KST):%H:%M:%S}"
            + (f" · {every}초마다 자동 새로고침" if auto else " · 자동 새로고침 꺼짐 (F5 로 새로고침)"))
    if not insp:
        ui.hero("INSPECTION STATUS", "볼트 전체의", "검사 현황", "플랜지별 볼트 상태와 최근 측정 기록을 한 화면에서 확인해요")
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

    # ---- 1. 맨 위: 큰 제목 + 전체 숫자 ----
    cnt = latest.final_result.value_counts()
    n_all = int(cnt.sum())
    pct_ok = 100 * cnt.get("OK", 0) / n_all if n_all else 0
    c1, c2 = st.columns([1, 1.15])
    with c1:
        ui.hero("INSPECTION STATUS", "볼트 전체의", "검사 현황", "플랜지별 볼트 상태와 최근 측정 기록을 한 화면에서 확인해요")
    with c2:
        ui.dark_total("총 검사 기록", f"{len(df)}", f"마지막 검사 {df.inspected_at.max():%m/%d %H:%M} · 플랜지 {latest.flange_id.nunique()}개", pct_ok)
    ui.stat3({k: int(cnt.get(k, 0)) for k in ("OK", "CHECK", "NG")}, n_all)
    st.caption(note + " · 숫자는 볼트별 최신 검사 기준")

    # ---- 2. 플랜지 카드 (나쁜 순서) ----
    t1, t2 = st.columns([1, 1], vertical_alignment="bottom")
    with t1:
        ui.h2("", "플랜지별", "볼트 상태.")
    with t2:
        with st.container(key="filter"):
            flt = st.segmented_control("보기", ["전체", "정상", "재측정", "이상 의심"], default="전체", label_visibility="collapsed") \
                if hasattr(st, "segmented_control") else st.radio("보기", ["전체", "정상", "재측정", "이상 의심"], horizontal=True, label_visibility="collapsed")
    want = {"정상": "OK", "재측정": "CHECK", "이상 의심": "NG"}.get(flt)
    cards = []
    for fid, g in latest.groupby("flange_id"):
        bolts = g[g.type == "BOLT"]
        res = worst(*g.final_result.tolist())
        f = fl_info.get(fid, {})
        total = int(f.get("bolt_count") or len(bolts))
        by_id = dict(zip(bolts.bolt_id, bolts.final_result))
        ids = [f"B{i:02d}" for i in range(1, total + 1)]
        extra = [b for b in by_id if b not in ids]                      # 번호 규칙이 다른 볼트도 빠뜨리지 않음
        dots = [by_id.get(b) for b in ids + extra]
        cards.append((RESULT_RANK.get(res, -1), fid, res, dots, g.inspected_at.max(),
                      int((bolts.final_result == "OK").sum()), int((bolts.final_result == "CHECK").sum()), int((bolts.final_result == "NG").sum())))
    cards = [c for c in sorted(cards, key=lambda c: (-c[0], c[1])) if want is None or c[2] == want]
    if not cards:
        st.caption("이 조건에 맞는 플랜지가 없어요.")
    cols = st.columns(4)
    for i, (_, fid, res, dots, last, n1, n2, n3) in enumerate(cards):
        with cols[i % 4]:
            ui.ring_card(fid, f"{last:%m-%d %H:%M}", dots, n1, n2, n3)

    # ---- 2-1. 추이 (어두운 카드) ----
    mic_col = "tapping.features.mic.peak_hz" if "tapping.features.mic.peak_hz" in df else "tapping.peak_hz"
    if mic_col in df:
        tr = df[(df.type == "BOLT")].dropna(subset=[mic_col]).sort_values("inspected_at").tail(30)
        if len(tr) >= 3:
            m, sd = tr[mic_col].mean(), tr[mic_col].std() or 0
            ui.trend_dark("음향 Peak 주파수 추이", f"최근 {len(tr)}회 · 연두 띠 = 이 그래프의 평균 ± 1σ (참고용, 판정 기준 아님)",
                          list(range(len(tr))), tr[mic_col].round(1).tolist(), (m - sd, m + sd) if sd else None)

    # ---- 2-2. 최근 측정 기록 ----
    ui.h2("", "최근", "측정 기록.")
    rc = df[(df.type == "BOLT") & df.final_result.notna()].sort_values("inspected_at", ascending=False)
    if "tapping.result" in rc:
        rc = rc[rc["tapping.result"].notna()]                          # 타음 측정 기록만 (시안과 같은 열)
    ui.table_card(TABLE_HEAD, table_rows(rc.head(10), mic_col))

    # ---- 3. 전체 검사 기록 (최근 측정 기록과 같은 표 모양) + 엑셀 ----
    g1, g2 = st.columns([1, 1], vertical_alignment="bottom")
    with g1:
        ui.h2("", "전체", "검사 기록.")
    c1, c2 = st.columns(2)
    sel_fl = c1.multiselect("플랜지", sorted(df.flange_id.unique()))
    sel_res = c2.multiselect("판정", ["정상", "재측정 필요", "체결 이상 의심"])
    view = df.copy()
    view["판정"] = view.final_result.map(ui.KO)
    if sel_fl:
        view = view[view.flange_id.isin(sel_fl)]
    if sel_res:
        view = view[view["판정"].isin(sel_res)]
    view = view.sort_values("inspected_at", ascending=False)
    cols_map = {"inspected_at": "검사시각", "flange_id": "플랜지", "bolt_id": "볼트", "inspector": "검사자",
                "판정": "판정", "tapping.features.mic.peak_hz": "음향 Peak(Hz)", "tapping.features.acc.peak_hz": "진동 Peak(Hz)",
                "tapping.score": "범위 이탈 수", "vision.protrusion_mm": "돌출(mm)", "vision.marking.gap_pct": "마킹 끊김(%)",
                "gap.gap_diff_mm": "틈 편차(mm)"}
    table = view[[c for c in cols_map if c in view.columns]].rename(columns=cols_map)
    buf = io.BytesIO()
    out = table.copy()
    out["검사시각"] = out["검사시각"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_excel(buf, index=False, sheet_name="검사기록")
    with g2:
        with st.container(key="xlsbtn"):
            st.download_button("엑셀 성적서 다운로드", buf.getvalue(), "bolt_inspection_report.xlsx")
    ui.table_card(TABLE_HEAD, table_rows(view, mic_col), max_h=460)
    st.caption(f"총 {len(view)}건 · 표 안에서 스크롤해서 볼 수 있어요")

    ui.cta("다음 볼트를<br>두드려 볼까요?", "다음 검사 하기", "/tapping")
    ui.footer()


st.fragment(page, run_every=f"{every}s" if auto else None)()
