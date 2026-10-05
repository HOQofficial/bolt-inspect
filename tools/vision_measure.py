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


def pair_boxes(nuts, tips):
    """너트 상자들과 볼트 끝 상자들 중 '같은 볼트'인 짝을 고름.
    nuts/tips = [(신뢰도, [x1, y1, x2, y2]), ...]
    조건: 볼트 끝의 가운데가 너트 가로 범위 안에 있고, 볼트 끝 위쪽이 너트 윗면보다 위에 있어야 함.
    반환: (점 3개, 신뢰도, 실패 이유)"""
    best = None
    for nc, n in nuts:
        nw = n[2] - n[0]
        for tc, t in tips:
            cx = (t[0] + t[2]) / 2
            inside = n[0] - 0.15 * nw <= cx <= n[2] + 0.15 * nw
            above = t[1] < n[1]
            close = t[3] >= n[1] - 0.5 * (n[3] - n[1])     # 볼트 끝 상자 아래쪽이 너트 윗면 근처
            if inside and above and close:
                score = min(nc, tc)
                if best is None or score > best[1]:
                    best = ([(n[0], n[1]), (n[2], n[3]), (cx, t[1])], score)
    if best:
        return best[0], best[1], None
    if not nuts or not tips:
        return None, 0.0, "너트나 볼트 끝을 찾지 못했어요"
    return None, 0.0, "너트와 볼트 끝을 찾았지만 같은 볼트로 이어지지 않아요 (옆모습 사진이 아니거나, 볼트 끝이 위를 향하지 않음)"


def detect(img, conf=0.35):
    """YOLO 로 nut / bolt_tip 상자를 찾아, 같은 볼트인 짝을 클릭 3점으로 바꿔 줌.
    반환: (점 3개 / 너트만 찾으면 점 2개 / None, 신뢰도, 메모 또는 None)"""
    global _model
    from ultralytics import YOLO
    if _model is None:
        _model = YOLO(str(MODEL_PATH))
    r = _model.predict(img, conf=conf, verbose=False)[0]
    found = {"nut": [], "bolt_tip": []}
    for b in r.boxes:
        name = r.names[int(b.cls)]
        if name in found:
            found[name].append((float(b.conf), [float(v) for v in b.xyxy[0]]))
    pts, score, why = pair_boxes(found["nut"], found["bolt_tip"])
    if pts is None and found["nut"]:
        # 볼트 끝 학습이 안 된 모델(너트만 앎)이거나 짝을 못 찾은 경우: 너트만 자동, 볼트 끝은 사람이 클릭
        nc, n = max(found["nut"], key=lambda t: t[0])
        return [(n[0], n[1]), (n[2], n[3])], nc, "너트만 찾았어요"
    return pts, score, why


# ---------------- I-마킹 (풀림 표시) ----------------
# 조인 뒤 볼트·너트·와셔(플랜지)에 한 줄로 그은 페인트 선. 너트가 돌면 너트 위 선이 옆으로 밀려 끊어짐.
# 판정값 gap_pct = (너트 위 마킹과 고정부 마킹 사이 가장 가까운 거리) / (너트 마킹 길이) × 100
MARK_COLORS = {"빨강": "red", "노랑": "yellow", "흰색": "white", "파랑": "blue", "초록": "green"}


def _seg_dist(p, a, b):
    """점 p 와 선분 ab 사이 거리"""
    p, a, b = (np.asarray(v, float) for v in (p, a, b))
    ab = b - a
    t = 0.0 if not ab.any() else float(np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0, 1))
    return float(np.linalg.norm(p - (a + t * ab)))


def mark_break_click(n1, n2, r1, r2):
    """클릭 4점: ①② 너트 위 마킹 양 끝, ③④ 고정부(와셔·플랜지) 마킹 양 끝.
    반환 dict(gap_pct, gap_px, nut_len_px, pair) — pair 는 가장 가까운 두 점(그림용)"""
    L = math.dist(n1, n2)
    if L < 5:
        raise ValueError("①② 가 너무 가깝습니다. 너트 위 마킹의 양 끝을 찍으세요.")
    cands = [(_seg_dist(p, r1, r2), p) for p in (n1, n2)] + [(_seg_dist(p, n1, n2), p) for p in (r1, r2)]
    d, _ = min(cands, key=lambda c: c[0])
    # 그림용: 너트 끝점 중 고정부 선분에 가장 가까운 점과, 고정부 끝점 중 너트 선분에 가장 가까운 점
    a = min((n1, n2), key=lambda p: _seg_dist(p, r1, r2))
    b = min((r1, r2), key=lambda p: _seg_dist(p, n1, n2))
    return {"gap_pct": round(100 * d / L, 1), "gap_px": round(d, 1), "nut_len_px": round(L, 1), "pair": (a, b)}


def color_mask(img, color):
    """페인트 색에 해당하는 픽셀 = True 인 2차원 배열. (PIL HSV: H 0~255)"""
    hsv = np.asarray(img.convert("RGB").convert("HSV")).astype(int)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if color == "red":
        return ((H <= 10) | (H >= 235)) & (S >= 100) & (V >= 70)
    if color == "yellow":
        return (H >= 22) & (H <= 50) & (S >= 100) & (V >= 100)
    if color == "green":
        return (H >= 60) & (H <= 115) & (S >= 80) & (V >= 60)
    if color == "blue":
        return (H >= 135) & (H <= 185) & (S >= 80) & (V >= 60)
    if color == "white":
        return (S <= 35) & (V >= 210)
    raise ValueError(color)


def mark_break_auto(img, nut_box, color, max_pts=3000):
    """너트 상자(①②)를 알 때, 색으로 마킹을 찾아 끊김을 계산. 사진은 볼트 끝이 '위'를 향해야 함.
    너트 상자 안 = 너트 마킹, 너트 아래(와셔·플랜지 쪽) = 고정부 마킹.
    반환 (dict 또는 None, 실패 이유)"""
    from scipy.spatial import cKDTree
    m = color_mask(img, color)
    x1, y1, x2, y2 = nut_box
    w, h = x2 - x1, y2 - y1
    ys, xs = np.nonzero(m)
    inside = (xs >= x1) & (xs <= x2) & (ys >= y1) & (ys <= y2)
    below = (xs >= x1 - 0.5 * w) & (xs <= x2 + 0.5 * w) & (ys > y2) & (ys <= y2 + h)
    if inside.sum() > 0.6 * w * h:
        return None, "너트 전체가 그 색으로 잡혔어요 (너트 색과 마킹 색이 비슷함). 직접 클릭하세요"
    if inside.sum() < 15:
        return None, "너트 위에서 마킹 색을 못 찾았어요. 색을 바꾸거나 직접 클릭하세요"
    if below.sum() < 15:
        return None, "너트 아래(와셔·플랜지)에서 마킹을 못 찾았어요. 사진 방향(볼트 끝이 위)을 확인하거나 직접 클릭하세요"
    A = np.column_stack([xs[inside], ys[inside]]).astype(float)
    B = np.column_stack([xs[below], ys[below]]).astype(float)
    rng = np.random.default_rng(0)
    if len(A) > max_pts:
        A = A[rng.choice(len(A), max_pts, replace=False)]
    if len(B) > max_pts:
        B = B[rng.choice(len(B), max_pts, replace=False)]
    # 1순위: 너트 아랫부분의 선 가운데 x 와, 너트 바로 아래(와셔)의 선 가운데 x 비교 (옆모습 기준)
    a_band = A[A[:, 1] >= y2 - 0.25 * h]
    b_band = B[B[:, 1] <= y2 + 0.15 * h]
    if len(a_band) >= 5 and len(b_band) >= 5:
        pa = (float(a_band[:, 0].mean()), float(a_band[:, 1].max()))
        pb = (float(b_band[:, 0].mean()), float(b_band[:, 1].min()))
        dist = abs(pa[0] - pb[0])
    else:   # 2순위: 두 색 덩어리 사이 가장 가까운 거리
        d, j = cKDTree(B).query(A)
        i = int(np.argmin(d))
        pa, pb, dist = tuple(A[i]), tuple(B[j[i]]), float(d[i])
    return {"gap_pct": round(100 * dist / max(h, 5), 1), "gap_px": round(dist, 1),
            "nut_len_px": round(float(h), 1), "pair": (pa, pb), "inside": A, "below": B}, None


def mark_overlay(img, nut_box, res):
    """자동 검출 결과 그림: 너트 마킹=분홍, 고정부 마킹=하늘, 가장 가까운 두 점 사이=노란 선"""
    from PIL import ImageDraw
    im = img.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    r = max(1, im.width // 400)
    for pts, c in ((res["inside"], (236, 72, 153)), (res["below"], (14, 165, 233))):
        for x, y in pts[:: max(1, len(pts) // 1500)]:
            d.rectangle([x - r, y - r, x + r, y + r], fill=c)
    d.rectangle(list(nut_box), outline=(37, 99, 235), width=max(2, im.width // 300))
    (ax, ay), (bx, by) = res["pair"]
    d.line([ax, ay, bx, by], fill=(250, 204, 21), width=max(3, im.width // 200))
    return im
