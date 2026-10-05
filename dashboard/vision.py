"""비전 검사 - 사진에서 볼트 돌출 길이 / 플랜지 틈을 mm 로 재고 판정·저장.

1단계(지금): 사진 위를 클릭해서 측정 -> 클릭이 그대로 학습 라벨로 저장됨
2단계(모델 학습 후): models/bolt_yolo.pt 가 있으면 AI 가 점을 자동으로 찍어 줌 (클릭으로 수정 가능)
"""
import hashlib
import io

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates

import store
import ui
from schema_rules import (MARK_LIMITS, SCHEMA_VERSION, judge_gap, judge_marking, judge_protrusion,
                          make_record_id, now_kst_iso)
import vision_measure as vm

APP_VERSION = "1.2"
PROT, MARK, GAP = "볼트 돌출", "I-마킹 (풀림 표시)", "플랜지 틈 (4지점)"
DISPLAY_W = 760
ss = st.session_state
ss.setdefault("v_pts", [])        # 볼트 돌출 클릭 점 (원본 좌표)
ss.setdefault("v_last", None)     # 마지막으로 처리한 클릭 (중복 방지)
ss.setdefault("v_img", None)      # 사진 해시
ss.setdefault("gap_vals", {})     # {"12": mm, ...}
ss.setdefault("g_pts", [])
ss.setdefault("v_saved", None)
ss.setdefault("m_pts", [])        # I-마킹 클릭 점
ss.setdefault("m_click", False)   # True = 자동 대신 직접 클릭
ss.setdefault("m_nut", None)      # AI 가 찾은 너트 상자


@st.cache_data(ttl=15)
def flanges():
    return {f["flange_id"]: f for f in store.list_flanges()}


def load_image(file, rotate):
    img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    return img.rotate(-rotate, expand=True) if rotate else img


def click_canvas(img, pts, labels, key, boxes=()):
    """사진 위에 지금까지 찍은 점·상자를 그려 보여 주고, 새 클릭을 원본 좌표로 돌려줌."""
    s = min(1.0, DISPLAY_W / img.width)
    disp = img.resize((int(img.width * s), int(img.height * s)))
    d = ImageDraw.Draw(disp)
    r = max(4, disp.width // 120)
    for (x1, y1, x2, y2), color in boxes:
        d.rectangle([x1 * s, y1 * s, x2 * s, y2 * s], outline=color, width=max(2, r // 2))
    for i, (x, y) in enumerate(pts):
        d.ellipse([x * s - r, y * s - r, x * s + r, y * s + r], fill="#ef4444", outline="white", width=2)
        d.text((x * s + r + 3, y * s - r - 3), labels[i] if i < len(labels) else str(i + 1), fill="#ef4444")
    v = streamlit_image_coordinates(disp, key=key)
    if v and (v["x"], v["y"], key) != ss.v_last:
        ss.v_last = (v["x"], v["y"], key)
        return (v["x"] / s, v["y"] / s)
    return None


FL = flanges()
if not FL:
    st.error("등록된 플랜지가 없습니다.")
    st.stop()

# ---------------- 사이드바 ----------------
with st.sidebar:
    st.header("비전 검사 설정")
    mode = st.radio("검사 종류", [PROT, MARK, GAP])
    fid = st.selectbox("플랜지", sorted(FL))
    f = FL[fid]
    bolt = (st.selectbox("볼트 (12시부터 시계방향)", [f"B{i:02d}" for i in range(1, f["bolt_count"] + 1)])
            if mode != GAP else "GAP")
    inspector = st.text_input("검사자", value=ss.get("inspector", "홍길동"), key="v_inspector")
    src = st.radio("사진", ["파일 올리기", "카메라로 찍기"], horizontal=True,
                   help="카메라는 PC 웹캠 또는 https 주소로 연 태블릿에서 동작")
    rotate = st.select_slider("사진 돌리기 (볼트 끝이 위로 오게)", [0, 90, 180, 270], value=0)
    CLOCKS = ["12", "3", "6", "9"]
    if mode == MARK:
        mcolor = st.radio("마킹 색", list(vm.MARK_COLORS), horizontal=True,
                          help="현장에서 그은 페인트 펜 색. 자동 검출에 씀")
    if mode == GAP:
        clock = st.radio("지금 찍는 지점", CLOCKS, horizontal=True, format_func=lambda c: f"{c}시",
                         help="지점마다 사진을 한 장씩 올려 4번 반복합니다")
        ref_mm = st.number_input("기준 길이 (mm)", value=float(f["nut_height_mm"]), step=0.1,
                                 help="사진 속 틈과 같은 깊이에 있는 아는 길이. 기본값 = 너트 높이")
    st.caption(f"{f['bolt_spec']} · 너트 높이 {f['nut_height_mm']} mm · 피치 {f['pitch_mm']} mm "
               f"· 돌출 허용 {f['limits']['protrusion_mm']['min']}~{f['limits']['protrusion_mm']['max']} mm")
    use_ai = vm.model_available() and st.toggle("AI 자동 점 찍기", value=True,
                                                help="models/bolt_yolo.pt 가 있을 때만 보입니다")
    if not vm.model_available():
        st.caption("AI 모델 없음 → 클릭 측정 모드. 학습 후 models/bolt_yolo.pt 를 넣으면 자동 모드가 켜집니다.")

st.title("비전 검사")
if mode == MARK:
    st.caption("조일 때 볼트·너트·와셔(플랜지)에 한 줄로 그어 둔 선이 그대로 이어져 있는지 봅니다. "
               "너트가 풀려 돌면 너트 위 선만 옆으로 밀려 끊어집니다.")
if mode == GAP:
    st.caption("12시 → 3시 → 6시 → 9시 순서로, 지점마다 사진 1장 + 클릭 4번")
    for c, k in zip(st.columns(4), CLOCKS):
        c.metric(f"{k}시 틈", f"{ss.gap_vals[k]:.2f} mm" if k in ss.gap_vals else "—")

file = (st.file_uploader("사진 올리기 (jpg, png)", type=["jpg", "jpeg", "png"])
        if src == "파일 올리기" else st.camera_input("볼트를 정면에서 찍으세요"))
if file is None:
    st.info("왼쪽에서 플랜지·볼트를 고르고 사진을 올리세요. 볼트가 세로로, 볼트 끝이 위로 오게 찍으면 됩니다."
            if mode == PROT else
            "마킹 선이 너트와 와셔(플랜지)에 걸쳐 보이게 옆에서 찍으세요. 자동 검출은 볼트 끝이 위로 와야 합니다."
            if mode == MARK else f"왼쪽에서 지금 찍는 지점({clock}시)을 확인하고 그 지점 사진을 올리세요.")
    st.stop()

raw = file.getvalue()
img = load_image(io.BytesIO(raw), rotate)
h = hashlib.md5(raw + bytes([rotate // 90]) + mode.encode()).hexdigest()
if ss.v_img != h:                       # 새 사진이면 점 초기화
    ss.v_img, ss.v_pts, ss.g_pts, ss.v_last, ss.v_saved = h, [], [], None, None
    ss.v_ai_msg = None
    ss.m_pts, ss.m_click, ss.m_nut = [], False, None
    if use_ai and mode == MARK:
        with st.spinner("AI 가 너트를 찾는 중..."):
            pts, conf, _ = vm.detect(img)
        if pts:
            ss.m_nut, ss.v_conf = vm.box_from_points(pts[0], pts[1]), conf
    if use_ai and mode == PROT:
        with st.spinner("AI 가 너트와 볼트 끝을 찾는 중..."):
            pts, conf, why = vm.detect(img)
        if pts and len(pts) == 3:
            ss.v_pts, ss.v_conf = pts, conf
            st.toast(f"AI 자동 검출 (신뢰도 {conf:.2f}). 틀리면 '다시 찍기' 후 클릭하세요.")
        elif pts:                          # 너트만 찾음 -> ③ 볼트 끝만 사람이 클릭
            ss.v_pts, ss.v_conf = pts, conf
            ss.v_ai_msg = f"AI 가 너트를 찾았어요 (신뢰도 {conf:.2f}). ③ 볼트 맨 끝만 클릭하세요. 너트 상자가 틀리면 '다시 찍기'."
        else:
            ss.v_ai_msg = f"AI 자동 측정 불가: {why}. 직접 클릭하세요."
            st.toast(ss.v_ai_msg)

# =====================================================================
if mode == PROT:
    if ss.get("v_ai_msg"):
        (st.info if ss.v_ai_msg.startswith("AI 가 너트") else st.warning)(ss.v_ai_msg)
    STEPS = ["① 너트 왼쪽 위 모서리", "② 너트 오른쪽 아래 모서리", "③ 볼트 맨 끝(가장 위)"]
    pts = ss.v_pts
    left, right = st.columns([3, 2])
    with right:
        if len(pts) < 3:
            ui.next_click("지금 클릭할 곳", STEPS[len(pts)], len(pts), len(STEPS))
            st.caption("사진 위를 클릭하세요. 확대가 필요하면 사진을 볼트 주변만 잘라서 올리면 더 정확합니다.")
        b1, b2 = st.columns(2)
        if b1.button("↶ 한 점 취소", width="stretch", disabled=not pts):
            ss.v_pts = pts[:-1]; st.rerun()
        if b2.button("다시 찍기", width="stretch", disabled=not pts):
            ss.v_pts = []; st.rerun()

    boxes = []
    if len(pts) >= 2:
        nut = vm.box_from_points(pts[0], pts[1]); boxes.append((nut, "#2563eb"))
        if len(pts) >= 3:
            boxes.append((vm.bolt_tip_box(pts[2], nut), "#16a34a"))
    with left:
        new = click_canvas(img, pts, ["①", "②", "③"], key=f"v_{h}", boxes=boxes)
    if new and len(pts) < 3:
        ss.v_pts = pts + [new]; st.rerun()

    if len(pts) == 3:
        nut, tip = vm.box_from_points(pts[0], pts[1]), pts[2]
        try:
            m = vm.protrusion(nut, tip, f["nut_height_mm"], f["pitch_mm"])
        except ValueError as e:
            st.error(str(e)); st.stop()
        auto = vm.count_threads_auto(np.asarray(img.convert("L")), tip, nut, f["pitch_mm"], m["mm_per_px"])
        res = judge_protrusion(m["protrusion_mm"], f["limits"]["protrusion_mm"])
        if m["protrusion_mm"] < 0:
            st.warning("③ 볼트 끝이 너트 윗면보다 아래에 찍혔어요. "
                       "볼트가 카메라를 정면으로 향한 사진(나사 끝 단면이 동그랗게 보임)이면 돌출 길이를 잴 수 없어요. "
                       "볼트가 세로로 서 있고 끝이 위를 향한 '옆모습' 사진을 쓰세요. "
                       "옆모습인데도 음수라면 볼트가 너트 밖으로 안 나온 것(체결 이상)이 맞아요.")
        lim = f["limits"]["protrusion_mm"]
        with right:
            ui.banner(f"{fid}-{bolt} 볼트 돌출", res,
                      f"{m['protrusion_mm']} mm (허용 {lim['min']}~{lim['max']} mm)")
            c1, c2, c3 = st.columns(3)
            c1.metric("돌출 길이", f"{m['protrusion_mm']} mm")
            c2.metric("나사산(계산)", f"{m['thread_count']} 산", help="돌출 길이 ÷ 피치")
            c3.metric("나사산(자동, 참고)", "-" if auto is None else f"{auto} 산",
                      help="사진 밝기 무늬로 센 값. 조명에 따라 틀릴 수 있어 판정에는 쓰지 않음")
            st.caption(f"배율 {m['mm_per_px']:.3f} mm/px (너트 높이 {f['nut_height_mm']} mm 기준)")
            caliper = st.number_input("캘리퍼 실측값 (mm, 정확도 평가용·선택)", min_value=0.0, value=0.0, step=0.1,
                                      help="입력하면 앱 측정값과의 오차가 기록되어 정확도 표에 들어갑니다")
            if ss.v_saved == h:
                st.success("저장 완료 ✓ (검사 기록 + 학습 라벨)")
            elif st.button("💾 저장 (검사 기록 + 학습 라벨)", type="primary", width="stretch"):
                tipbox = vm.bolt_tip_box(tip, nut)
                at = now_kst_iso()
                vision = {"protrusion_mm": m["protrusion_mm"], "thread_count": m["thread_count"],
                          "confidence": round(float(ss.get("v_conf", 1.0)) if use_ai else 1.0, 2),
                          "crop_jpg_b64": vm.crop_b64(img, (nut[0], tipbox[1], nut[2], nut[3])), "result": res}
                doc = {"schema_version": SCHEMA_VERSION, "record_id": make_record_id(fid, bolt, at), "type": "BOLT",
                       "flange_id": fid, "bolt_id": bolt, "inspector": inspector or "미입력", "device_id": "PC-VISION",
                       "inspected_at": at, "vision": vision, "gap": None, "tapping": None,
                       "final_result": res, "app_version": APP_VERSION}
                store.save_inspection(doc)
                stem = vm.stem_for(fid, bolt)
                vm.save_label(img, stem, nut, tipbox)
                vm.append_truth({"file": f"{stem}.jpg", "flange_id": fid, "bolt_id": bolt, "bolt_spec": f["bolt_spec"],
                                 "protrusion_mm_app": m["protrusion_mm"], "thread_count_app": m["thread_count"],
                                 "thread_count_auto": "" if auto is None else auto,
                                 "protrusion_mm_caliper": caliper or "", "taken_by": inspector, "taken_at": at})
                ss.v_saved = h
                st.cache_data.clear()
                st.rerun()

# =====================================================================
elif mode == MARK:
    color = vm.MARK_COLORS[mcolor]
    left, right = st.columns([3, 2])
    nut_box, got, crop_box = ss.m_nut, None, None
    auto, why = (vm.mark_break_auto(img, nut_box, color) if nut_box and not ss.m_click else (None, None))
    if auto:                                    # ---- 자동: 색으로 찾음
        got = {"gap_pct": auto["gap_pct"], "method": "auto"}
        crop_box = nut_box
        with left:
            st.image(vm.mark_overlay(img, nut_box, auto), width="stretch",
                     caption="분홍 = 너트 위 마킹 · 하늘 = 와셔·플랜지 마킹 · 노란 선 = 끊긴 거리")
        with right:
            st.caption(f"AI 너트 검출 (신뢰도 {ss.get('v_conf', 0):.2f}) + '{mcolor}' 색 자동 검출. "
                       "색이 엉뚱한 곳에 잡혔으면 아래 버튼으로 직접 찍으세요.")
            if st.button("직접 클릭으로 하기", width="stretch"):
                ss.m_click = True; st.rerun()
    else:                                       # ---- 직접 클릭 4번
        if why:
            st.info(f"자동 검출 안 됨: {why}")
        elif not nut_box and not ss.m_click and use_ai:
            st.info("AI 가 너트를 못 찾았어요. 마킹 선 끝을 직접 4번 클릭하세요.")
        STEPS = ["① 너트 위 마킹 한쪽 끝", "② 너트 위 마킹 반대쪽 끝",
                 "③ 와셔·플랜지 마킹 한쪽 끝 (너트 쪽)", "④ 와셔·플랜지 마킹 반대쪽 끝"]
        pts = ss.m_pts
        with right:
            if len(pts) < 4:
                ui.next_click("지금 클릭할 곳", STEPS[len(pts)], len(pts), len(STEPS))
                st.caption("너트에 그어진 선의 양 끝(①②), 너트 바로 아래 와셔·플랜지에 그어진 선의 양 끝(③④)을 찍으세요.")
            b1, b2 = st.columns(2)
            if b1.button("↶ 한 점 취소", width="stretch", disabled=not pts):
                ss.m_pts = pts[:-1]; st.rerun()
            if b2.button("다시 찍기", width="stretch", disabled=not pts):
                ss.m_pts = []; st.rerun()
            if ss.m_click and nut_box and st.button("자동 검출로 돌아가기", width="stretch"):
                ss.m_click, ss.m_pts = False, []; st.rerun()
        with left:
            new = click_canvas(img, pts, ["①", "②", "③", "④"], key=f"m_{h}")
        if new and len(pts) < 4:
            ss.m_pts = pts + [new]; st.rerun()
        if len(pts) == 4:
            try:
                r = vm.mark_break_click(*pts)
            except ValueError as e:
                st.error(str(e)); st.stop()
            got = {"gap_pct": r["gap_pct"], "method": "click"}
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            crop_box = (min(xs), min(ys), max(xs), max(ys))

    if got:
        res = judge_marking(got["gap_pct"])
        with right:
            ui.banner(f"{fid}-{bolt} I-마킹", res,
                      f"끊김 {got['gap_pct']}% (정상 ≤ {MARK_LIMITS['ok']:.0f}%, 재측정 ≤ {MARK_LIMITS['check']:.0f}%)")
            st.metric("마킹 끊김", f"{got['gap_pct']} %",
                      help="너트 위 선과 와셔·플랜지 선 사이의 가장 가까운 거리 ÷ 너트 위 선 길이. 0% = 완전히 이어짐")
            st.caption("너트가 약 10° 돌면 10% 정도 어긋납니다. 선이 원래 비뚤게 그어졌으면 재측정이 나올 수 있어요.")
            key = f"mark-{h}"
            if ss.v_saved == key:
                st.success("저장 완료 ✓")
            elif st.button("💾 저장 (검사 기록)", type="primary", width="stretch"):
                at = now_kst_iso()
                vision = {"protrusion_mm": None, "thread_count": None,
                          "confidence": round(float(ss.get("v_conf", 1.0)), 2) if got["method"] == "auto" else 1.0,
                          "crop_jpg_b64": vm.crop_b64(img, crop_box, pad=0.6), "result": res,
                          "marking": {**got, "color": color, "result": res}}
                doc = {"schema_version": SCHEMA_VERSION, "record_id": make_record_id(fid, bolt, at), "type": "BOLT",
                       "flange_id": fid, "bolt_id": bolt, "inspector": inspector or "미입력", "device_id": "PC-VISION",
                       "inspected_at": at, "vision": vision, "gap": None, "tapping": None,
                       "final_result": res, "app_version": APP_VERSION}
                store.save_inspection(doc)
                ss.v_saved = key
                st.cache_data.clear()
                st.rerun()

# =====================================================================
else:
    STEPS = ["① 기준 길이 시작 (예: 너트 윗면)", "② 기준 길이 끝 (예: 너트 아랫면)", "③ 위 플랜지 면", "④ 아래 플랜지 면"]
    done = ss.gap_vals

    pts = ss.g_pts
    left, right = st.columns([3, 2])
    with right:
        if len(pts) < 4:
            ui.next_click(f"{clock}시 지점 — 지금 클릭할 곳", STEPS[len(pts)], len(pts), len(STEPS))
        b1, b2 = st.columns(2)
        if b1.button("↶ 한 점 취소", width="stretch", disabled=not pts):
            ss.g_pts = pts[:-1]; st.rerun()
        if b2.button("다시 찍기", width="stretch", disabled=not pts):
            ss.g_pts = []; st.rerun()
    with left:
        new = click_canvas(img, pts, ["①", "②", "③", "④"], key=f"g_{h}")
    if new and len(pts) < 4:
        ss.g_pts = pts + [new]; st.rerun()
    if len(pts) == 4:
        try:
            g = vm.gap_mm(pts[0], pts[1], ref_mm, pts[2], pts[3])
        except ValueError as e:
            st.error(str(e)); st.stop()
        with right:
            st.metric(f"{clock}시 틈", f"{g:.2f} mm")
            if st.button(f"✓ {clock}시 값으로 저장하고 다음 지점", type="primary", width="stretch"):
                ss.gap_vals = {**done, clock: g}
                ss.g_pts = []
                st.toast(f"{clock}시 = {g:.2f} mm. 다음 지점 사진을 올리고 왼쪽에서 지점을 바꾸세요.")
                st.rerun()

    if len(done) == 4:
        vals = [done[k] for k in CLOCKS]
        diff, res = judge_gap(vals, f["limits"]["gap_mm"])
        lim = f["limits"]["gap_mm"]
        ui.banner(f"{fid} 플랜지 틈 (4지점)", res,
                  f"편차 {diff:.2f} mm (허용 {lim['max_diff']} mm) · 범위 {lim['min']}~{lim['max']} mm")
        if ss.v_saved == f"gap-{fid}-{vals}":
            st.success("저장 완료 ✓")
        elif st.button("💾 틈 검사 저장", type="primary"):
            at = now_kst_iso()
            doc = {"schema_version": SCHEMA_VERSION, "record_id": make_record_id(fid, "GAP", at), "type": "GAP",
                   "flange_id": fid, "bolt_id": "GAP", "inspector": inspector or "미입력", "device_id": "PC-VISION",
                   "inspected_at": at, "vision": None, "gap": {"gap_mm": vals, "gap_diff_mm": diff, "result": res},
                   "tapping": None, "final_result": res, "app_version": APP_VERSION}
            store.save_inspection(doc)
            ss.v_saved = f"gap-{fid}-{vals}"
            st.cache_data.clear()
            st.rerun()
        if st.button("4지점 값 초기화"):
            ss.gap_vals = {}; st.rerun()

# ---------------- 정확도 (캘리퍼와 비교) ----------------
st.divider()
st.subheader("정확도 (앱 측정 vs 캘리퍼)")
rows = [r for r in vm.read_truth() if r.get("protrusion_mm_caliper")]
if rows:
    t = pd.DataFrame(rows)
    t["오차(mm)"] = (t.protrusion_mm_app.astype(float) - t.protrusion_mm_caliper.astype(float)).round(2)
    a, b, c = st.columns(3)
    a.metric("비교한 사진", len(t))
    b.metric("평균 오차", f"{t['오차(mm)'].abs().mean():.2f} mm")
    c.metric("최대 오차", f"{t['오차(mm)'].abs().max():.2f} mm")
    st.dataframe(t[["file", "bolt_spec", "protrusion_mm_app", "protrusion_mm_caliper", "오차(mm)"]]
                 .rename(columns={"protrusion_mm_app": "앱(mm)", "protrusion_mm_caliper": "캘리퍼(mm)"}),
                 hide_index=True, width="stretch")
else:
    st.caption("저장할 때 캘리퍼 실측값을 넣으면 여기에 오차 표가 생깁니다. 발표용 정확도 수치가 됩니다.")
n_lbl = len(list((vm.LABEL_DIR / "labels").glob("*.txt"))) if (vm.LABEL_DIR / "labels").exists() else 0
st.caption(f"쌓인 학습 라벨: {n_lbl}장 (data/labels) — 50장이 넘으면 AI 학습을 시작할 수 있어요.")
