"""비전 측정 계산 (스키마 v1.1 의 vision / gap 객체를 만드는 데 필요한 순수 함수들).

좌표는 모두 '원본 사진 픽셀' 기준 (x 오른쪽, y 아래쪽).
볼트는 사진에서 '세로로 서 있고, 볼트 끝이 위쪽'을 향한다고 가정합니다(앱에서 사진을 돌려 맞춤).

볼트 돌출:  클릭 3번
  ① 너트 왼쪽 위 모서리  ② 너트 오른쪽 아래 모서리  ③ 볼트 맨 끝(가장 위)
  배율(mm/px) = 너트 높이(mm) / 너트 높이(px)   <- 너트 '폭'이 아니라 '높이'를 자로 씀
  돌출(mm)    = (너트 윗면 y - 볼트 끝 y) × 배율
플랜지 틈:  지점마다 클릭 4번
  ① 기준 길이 시작 ② 기준 길이 끝 (예: 너트 위·아래 끝)  ③ 위 플랜지 면 ④ 아래 플랜지 면
  틈(mm) = |③-④| / |①-②| × 기준 길이(mm)
"""
import base64
import csv
import io
import math
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LABEL_DIR = ROOT / "data" / "labels"          # YOLO 형식 학습 데이터가 쌓이는 곳
TRUTH_CSV = ROOT / "data" / "truth_vision.csv"
CLASSES = ["nut", "bolt_tip"]                   # Roboflow 프로젝트 클래스와 같은 순서
BOLT_TO_NUT_WIDTH = 0.67                        # 볼트 지름 ≈ 너트 맞변 × 0.67 (M16: 16/24)


def box_from_points(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def bolt_tip_box(tip, nut_box):
    """볼트 끝 ~ 너트 윗면 사이의 돌출부 상자 (라벨용)"""
    x1, y1, x2, _ = nut_box
    half = (x2 - x1) * BOLT_TO_NUT_WIDTH / 2
    return (tip[0] - half, min(tip[1], y1), tip[0] + half, max(tip[1], y1))


def protrusion(nut_box, tip, nut_height_mm, pitch_mm):
    """반환: dict(protrusion_mm, thread_count, mm_per_px)"""
    nut_h_px = nut_box[3] - nut_box[1]
    if nut_h_px <= 2:
        raise ValueError("너트 상자가 너무 작습니다. ①②를 너트 모서리에 다시 찍으세요.")
    mm_per_px = nut_height_mm / nut_h_px
    mm = (nut_box[1] - tip[1]) * mm_per_px
    return {"protrusion_mm": round(mm, 1),
            "thread_count": max(0, int(round(mm / pitch_mm))) if pitch_mm else None,
            "mm_per_px": mm_per_px}


def count_threads_auto(gray, tip, nut_box, pitch_mm, mm_per_px):
    """돌출부를 볼트 축 방향으로 잘라 밝기 봉우리(나사산) 개수를 셈. 참고값 (조명에 민감).
    gray: 2차원 numpy 배열(흑백). 실패하면 None."""
    from scipy.signal import find_peaks
    x1, y1, x2, y2 = [int(round(v)) for v in bolt_tip_box(tip, nut_box)]
    w = max(2, (x2 - x1) // 3)
    cx = int(round(tip[0]))
    strip = gray[max(0, y1):max(0, y2), max(0, cx - w // 2):cx + w // 2 + 1]
    if strip.shape[0] < 8 or strip.shape[1] < 1:
        return None
    prof = strip.mean(axis=1).astype(float)
    k = max(3, len(prof) // 6) | 1
    prof = prof - np.convolve(prof, np.ones(k) / k, mode="same")      # 천천히 변하는 밝기 제거
    pitch_px = pitch_mm / mm_per_px
    peaks, _ = find_peaks(prof, distance=max(2, int(pitch_px * 0.6)), prominence=np.std(prof) * 0.5)
    return int(len(peaks))


def gap_mm(s1, s2, ref_mm, g1, g2):
    ref_px = math.dist(s1, s2)
    if ref_px <= 2:
        raise ValueError("기준 길이 두 점이 너무 가깝습니다.")
    return round(math.dist(g1, g2) / ref_px * ref_mm, 2)


def crop_b64(img, box, max_side=320, pad=0.25):
    """볼트 주변만 잘라 작은 JPEG(base64)로. 스키마 한도 140,000자 안에 들어가게 함."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    c = img.crop((max(0, x1 - w * pad), max(0, y1 - h * pad), min(img.width, x2 + w * pad), min(img.height, y2 + h * pad)))
    c.thumbnail((max_side, max_side))
    for q in (70, 50, 35):
        buf = io.BytesIO()
        c.convert("RGB").save(buf, "JPEG", quality=q)
        s = base64.b64encode(buf.getvalue()).decode()
        if len(s) <= 140000:
            return s
    return None


def save_label(img, stem, nut_box, tip_box):
    """사진 + YOLO 라벨(txt)을 data/labels 에 저장. Roboflow 에 폴더째 올리면 됨."""
    (LABEL_DIR / "images").mkdir(parents=True, exist_ok=True)
    (LABEL_DIR / "labels").mkdir(parents=True, exist_ok=True)
    W, H = img.size
    lines = []
    for cls, (x1, y1, x2, y2) in ((0, nut_box), (1, tip_box)):
        lines.append(f"{cls} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} {(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}")
    img.convert("RGB").save(LABEL_DIR / "images" / f"{stem}.jpg", quality=92)
    (LABEL_DIR / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    yaml = LABEL_DIR / "data.yaml"
    if not yaml.exists():
        yaml.write_text("path: .\ntrain: images\nval: images\nnames:\n  0: nut\n  1: bolt_tip\n", encoding="utf-8")
    return LABEL_DIR / "images" / f"{stem}.jpg"


TRUTH_COLS = ["file", "flange_id", "bolt_id", "bolt_spec", "protrusion_mm_app", "thread_count_app",
              "thread_count_auto", "protrusion_mm_caliper", "taken_by", "taken_at"]


def append_truth(row):
    new = not TRUTH_CSV.exists()
    TRUTH_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(TRUTH_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=TRUTH_COLS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in TRUTH_COLS})


def read_truth():
    if not TRUTH_CSV.exists():
        return []
    with open(TRUTH_CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def stem_for(flange_id, bolt_id):
    return f"{flange_id}_{bolt_id}_{datetime.now():%Y%m%d_%H%M%S}"


# ---------------- AI 자동 검출 (모델이 있을 때만) ----------------
MODEL_PATH = ROOT / "models" / "bolt_yolo.pt"


def model_available():
    if not MODEL_PATH.exists():
        return False
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


_model = None


def detect(img, conf=0.35):
    """YOLO 로 nut / bolt_tip 상자를 찾아 클릭 3점으로 바꿔 줌. 못 찾으면 None.
    반환: [너트 왼쪽위, 너트 오른쪽아래, 볼트 끝], 신뢰도"""
    global _model
    from ultralytics import YOLO
    if _model is None:
        _model = YOLO(str(MODEL_PATH))
    r = _model.predict(img, conf=conf, verbose=False)[0]
    best = {}
    for b in r.boxes:
        name = r.names[int(b.cls)]
        c = float(b.conf)
        if name in CLASSES and c > best.get(name, (0, None))[0]:
            best[name] = (c, [float(v) for v in b.xyxy[0]])
    if "nut" not in best or "bolt_tip" not in best:
        return None, 0.0
    (nc, n), (tc, t) = best["nut"], best["bolt_tip"]
    return [(n[0], n[1]), (n[2], n[3]), ((t[0] + t[2]) / 2, t[1])], min(nc, tc)
