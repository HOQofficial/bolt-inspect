"""공개 데이터(Roboflow zip) + 우리가 만든 라벨을 하나의 학습 세트로 합칩니다.

사용법:
  1) Roboflow Universe 에서 받은 zip 들을 data/public_zips/ 폴더에 그대로 넣기 (압축 풀지 않아도 됨)
  2) python tools/merge_public_data.py
  3) 결과: data/train_set/        (YOLO 학습 폴더, data.yaml 포함)
           data/train_set.zip     (Colab 에 올릴 파일)
           data/train_set_preview/ (상자가 제대로 붙었는지 눈으로 확인하는 사진)

클래스 이름 바꾸기 규칙 (데이터셋마다 이름이 달라서 자동으로 맞춤):
  'nut' 이 들어간 이름        -> nut       (예: nut_m16)
  'bolt_point' 또는 'tip'     -> bolt_tip  (예: bolt_point_m16)
  그 밖의 클래스              -> 버림 (화면에 목록이 나옴)

직접 정하고 싶으면 data/public_zips/class_map.txt 에 한 줄씩 적기 (자동 규칙보다 우선):
  bolt_b = nut
  bolt nut = nut
  Bolt_Loose = 버림

옵션:
  --need-both   너트와 볼트 끝이 '둘 다' 라벨된 사진만 씀 (권장).
                한쪽만 라벨된 사진은 AI 에게 "저건 볼트 끝 아님" 이라고 잘못 가르치기 때문.
"""
import random
import re
import shutil
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ZIPS = ROOT / "data" / "public_zips"
OURS = ROOT / "data" / "labels"
OUT = ROOT / "data" / "train_set"
PREVIEW = ROOT / "data" / "train_set_preview"
TMP = ROOT / "data" / "_unzipped"
CLASSES = ["nut", "bolt_tip"]
CLASS_MAP_FILE = ZIPS / "class_map.txt"
NEED_BOTH = "--need-both" in sys.argv
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_class_map():
    m = {}
    if CLASS_MAP_FILE.exists():
        for line in CLASS_MAP_FILE.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = (t.strip() for t in line.split("=", 1))
                m[k.lower()] = v if v in CLASSES else None
    return m


CUSTOM = load_class_map()


def map_name(name):
    low = name.lower()
    if low in CUSTOM:
        return CUSTOM[low]
    if "bolt_point" in low or "tip" in low:
        return "bolt_tip"
    if "nut" in low:
        return "nut"
    return None


def read_names(yaml_path):
    """data.yaml 의 names 를 읽음 (리스트 형식 / 번호: 이름 형식 둘 다)"""
    text = yaml_path.read_text(encoding="utf-8")
    m = re.search(r"names:\s*\[(.*?)\]", text, re.S)
    if m:
        return [s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()]
    names = {}
    block = text.split("names:", 1)[1] if "names:" in text else ""
    for line in block.splitlines()[1:]:
        mm = re.match(r"\s+(\d+)\s*:\s*(.+)", line)
        if mm:
            names[int(mm.group(1))] = mm.group(2).strip().strip("'\"")
        elif re.match(r"\s+-\s*(.+)", line):
            names[len(names)] = re.match(r"\s+-\s*(.+)", line).group(1).strip().strip("'\"")
        elif line.strip() and not line.startswith((" ", "\t")):
            break
    return [names[k] for k in sorted(names)]


def copy_pair(img, lbl, names, split, prefix, stats, dropped):
    lines = []
    if lbl.exists():
        for line in lbl.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:          # 상자(5칸)가 아닌 다각형 라벨은 건너뜀
                continue
            src = names[int(parts[0])] if int(parts[0]) < len(names) else f"#{parts[0]}"
            dst = map_name(src)
            if dst is None:
                dropped[src] = dropped.get(src, 0) + 1
                continue
            lines.append(" ".join([str(CLASSES.index(dst))] + parts[1:]))
    if not lines:
        return False
    if NEED_BOTH and len({l.split()[0] for l in lines}) < 2:
        stats["skipped"] = stats.get("skipped", 0) + 1
        return False
    for l in lines:
        stats[CLASSES[int(l.split()[0])]] += 1
    stem = f"{prefix}__{img.stem}"[:150]
    shutil.copy(img, OUT / "images" / split / f"{stem}{img.suffix.lower()}")
    (OUT / "labels" / split / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def preview(n_per_source=3):
    shutil.rmtree(PREVIEW, ignore_errors=True)
    PREVIEW.mkdir(parents=True)
    seen = {}
    colors = {0: "#2563eb", 1: "#16a34a"}
    for img in sorted((OUT / "images" / "train").glob("*")):
        src = img.stem.split("__")[0]
        if seen.get(src, 0) >= n_per_source:
            continue
        seen[src] = seen.get(src, 0) + 1
        im = Image.open(img).convert("RGB")
        d = ImageDraw.Draw(im)
        W, H = im.size
        for line in (OUT / "labels" / "train" / f"{img.stem}.txt").read_text().splitlines():
            c, x, y, w, h = line.split()
            c, x, y, w, h = int(c), float(x) * W, float(y) * H, float(w) * W, float(h) * H
            d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], outline=colors[c], width=max(2, W // 200))
            d.text((x - w / 2 + 3, y - h / 2 + 2), CLASSES[c], fill=colors[c])
        im.save(PREVIEW / f"{img.stem}.jpg", quality=85)


def main():
    zips = sorted(ZIPS.glob("*.zip")) if ZIPS.exists() else []
    has_ours = (OURS / "labels").exists() and any((OURS / "labels").glob("*.txt"))
    if not zips and not has_ours:
        sys.exit(f"합칠 데이터가 없습니다. Roboflow 에서 받은 zip 을 {ZIPS} 에 넣으세요.")

    shutil.rmtree(OUT, ignore_errors=True)
    shutil.rmtree(TMP, ignore_errors=True)
    for s in ("train", "val"):
        (OUT / "images" / s).mkdir(parents=True)
        (OUT / "labels" / s).mkdir(parents=True)

    report, dropped = [], {}
    for z in zips:
        prefix = re.sub(r"[^A-Za-z0-9]+", "_", z.stem)[:40]
        dest = TMP / prefix
        with zipfile.ZipFile(z) as f:
            f.extractall(dest)
        yamls = list(dest.rglob("data.yaml"))
        if not yamls:
            print(f"[건너뜀] {z.name}: data.yaml 이 없습니다. 'YOLOv11' 형식으로 받았는지 확인하세요.")
            continue
        base = yamls[0].parent
        names = read_names(yamls[0])
        stats = {"nut": 0, "bolt_tip": 0}
        n = 0
        for split_dir, split in (("train", "train"), ("valid", "val"), ("val", "val"), ("test", "val")):
            img_dir = base / split_dir / "images"
            if not img_dir.exists():
                continue
            for img in img_dir.iterdir():
                if img.suffix.lower() in IMG_EXT:
                    n += copy_pair(img, base / split_dir / "labels" / f"{img.stem}.txt", names, split, prefix, stats, dropped)
        report.append((z.name, names, n, stats))

    if has_ours:   # 비전 검사 페이지에서 저장한 우리 라벨 (80:20 으로 나눔)
        stats, n = {"nut": 0, "bolt_tip": 0}, 0
        imgs = sorted((OURS / "images").glob("*.jpg"))
        random.Random(0).shuffle(imgs)
        for k, img in enumerate(imgs):
            split = "val" if k < max(1, len(imgs) // 5) and len(imgs) >= 5 else "train"
            n += copy_pair(img, OURS / "labels" / f"{img.stem}.txt", CLASSES, split, "ours", stats, dropped)
        report.append(("우리 라벨 (data/labels)", CLASSES, n, stats))

    (OUT / "data.yaml").write_text(
        "# Colab 에서는 path 를 압축 푼 위치로 바꿔서 씀 (가이드 4단계 코드가 자동으로 함)\n"
        "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: nut\n  1: bolt_tip\n", encoding="utf-8")
    shutil.rmtree(TMP, ignore_errors=True)
    preview()
    zpath = OUT.parent / "train_set.zip"
    zpath.unlink(missing_ok=True)
    shutil.make_archive(str(zpath.with_suffix("")), "zip", OUT)

    n_tr = len(list((OUT / "images" / "train").glob("*")))
    n_va = len(list((OUT / "images" / "val").glob("*")))
    print("\n=== 합치기 결과 ===")
    for name, names, n, st in report:
        skip = f" | 한쪽만 있어 뺀 사진 {st['skipped']}장" if st.get("skipped") else ""
        print(f"- {name}: 사진 {n}장 | nut {st['nut']}개, bolt_tip {st['bolt_tip']}개{skip} | 원래 클래스 {names}")
    if dropped:
        print(f"- 버린 클래스(우리 목적과 무관): {dropped}")
    print(f"\n학습용 {n_tr}장 / 검증용 {n_va}장  ->  {OUT}")
    print(f"Colab 에 올릴 파일: {zpath}  ({zpath.stat().st_size / 1e6:.1f} MB)")
    print(f"확인용 사진: {PREVIEW}  (파란 상자=nut, 초록 상자=bolt_tip 이 맞게 붙었는지 보세요)")
    if n_tr + n_va < 100:
        print("\n참고: 100장보다 적습니다. 데이터셋을 몇 개 더 받으면 AI 가 더 안정적입니다.")


if __name__ == "__main__":
    main()
