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
from schema_rules import (SCHEMA_VERSION, judge_gap, judge_protrusion, make_record_id,
                          now_kst_iso)
import vision_measure as vm

APP_VERSION = "1.1"
DISPLAY_W = 760
ss = st.session_state
ss.setdefault("v_pts", [])        # 볼트 돌출 클릭 점 (원본 좌표)
ss.setdefault("v_last", None)     # 마지막으로 처리한 클릭 (중복 방지)
ss.setdefault("v_img", None)      # 사진 해시
ss.setdefault("gap_vals", {})     # {"12": mm, ...}
ss.setdefault("g_pts", [])
ss.setdefault("v_saved", None)


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
    mode = st.radio("검사 종류", ["볼트 돌출", "플랜지 틈 (4지점)"])
    fid = st.selectbox("플랜지", sorted(FL))
    f = FL[fid]
    bolt = (st.selectbox("볼트 (12시부터 시계방향)", [f"B{i:02d}" for i in range(1, f["bolt_count"] + 1)])
            if mode == "볼트 돌출" else "GAP")
    inspector = st.text_input("검사자", value=ss.get("inspector", "홍길동"), key="v_inspector")
    src = st.radio("사진", ["파일 올리기", "카메라로 찍기"], horizontal=True,
                   help="카메라는 PC 웹캠 또는 https 주소로 연 태블릿에서 동작")
    rotate = st.select_slider("사진 돌리기 (볼트 끝이 위로 오게)", [0, 90, 180, 270], value=0)
    CLOCKS = ["12", "3", "6", "9"]
    if mode != "볼트 돌출":
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
if mode != "볼트 돌출":
    st.caption("12시 → 3시 → 6시 → 9시 순서로, 지점마다 사진 1장 + 클릭 4번")
    for c, k in zip(st.columns(4), CLOCKS):
        c.metric(f"{k}시 틈", f"{ss.gap_vals[k]:.2f} mm" if k in ss.gap_vals else "—")

file = (st.file_uploader("사진 올리기 (jpg, png)", type=["jpg", "jpeg", "png"])
        if src == "파일 올리기" else st.camera_input("볼트를 정면에서 찍으세요"))
if file is None:
    st.info("왼쪽에서 플랜지·볼트를 고르고 사진을 올리세요. 볼트가 세로로, 볼트 끝이 위로 오게 찍으면 됩니다."
            if mode == "볼트 돌출" else f"왼쪽에서 지금 찍는 지점({clock}시)을 확인하고 그 지점 사진을 올리세요.")
    st.stop()

raw = file.getvalue()
img = load_image(io.BytesIO(raw), rotate)
h = hashlib.md5(raw + bytes([rotate // 90]) + mode.encode()).hexdigest()
if ss.v_img != h:                       # 새 사진이면 점 초기화
    ss.v_img, ss.v_pts, ss.g_pts, ss.v_last, ss.v_saved = h, [], [], None, None
    if use_ai and mode == "볼트 돌출":
        with st.spinner("AI 가 너트와 볼트 끝을 찾는 중..."):
            pts, conf = vm.detect(img)
        if pts:
            ss.v_pts, ss.v_conf = pts, conf
            st.toast(f"AI 자동 검출 (신뢰도 {conf:.2f}). 틀리면 '다시 찍기' 후 클릭하세요.")
        else:
            st.toast("AI 가 찾지 못했습니다. 직접 클릭하세요.")

# =====================================================================
if mode == "볼트 돌출":
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
