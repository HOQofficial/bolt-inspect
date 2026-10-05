"""가짜 데이터 만들기: sample/fake_flanges.json, sample/fake_inspections.json

실행:  python tools/make_fake_data.py
대시보드·앱을 실제 데이터 없이 먼저 만들어 볼 때 씁니다. 만든 뒤 스키마 검사까지 자동으로 합니다.
"""
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from schema_rules import (KST, SCHEMA_VERSION, calc_tap_ref, judge_gap, judge_marking, judge_protrusion,
                          make_record_id, tapping_from_features, validate, worst)
from sim import mock_features

random.seed(7)
nprng = np.random.default_rng(7)
OUT = Path(__file__).resolve().parent.parent / "sample"
OUT.mkdir(exist_ok=True)

SPECS = {"M16": (14.8, 2.0), "M20": (18.0, 2.5), "M24": (21.5, 3.0)}  # 너트 높이, 피치
ZONES = ["엔진룸-1층", "엔진룸-2층", "펌프룸", "보일러실"]
PEOPLE = ["김현장", "이검사", "박안전"]

flanges = []
for i in range(1, 7):
    spec = random.choice(list(SPECS))
    nut_h, pitch = SPECS[spec]
    count = random.choice([4, 8])
    flanges.append({
        "schema_version": SCHEMA_VERSION,
        "flange_id": f"FL{i:03d}",
        "zone": random.choice(ZONES),
        "bolt_spec": spec,
        "bolt_count": count,
        "nut_height_mm": nut_h,
        "pitch_mm": pitch,
        "limits": {"protrusion_mm": {"min": 2 * pitch, "max": 8 * pitch},
                   "gap_mm": {"min": 1.5, "max": 3.5, "max_diff": 0.8}},
        "tap_baseline": {f"B{b:02d}": {"peak_hz": round(random.uniform(2800, 3400)), "std_hz": 40, "n": 10}
                         for b in range(1, count + 1)},
        "updated_at": datetime(2026, 10, 5, 9, 0, tzinfo=KST).isoformat(),
        # v1.1: 정상 볼트 10회 측정으로 등록한 범위 기준
        "tap_ref": {**calc_tap_ref([mock_features("정상 체결", nprng) for _ in range(10)], 3.0),
                    "registered_at": datetime(2026, 10, 5, 9, 30, tzinfo=KST).isoformat()},
    })

inspections = []
start = datetime(2026, 10, 6, 9, 0, tzinfo=KST)
for f in flanges:
    for day in range(3):
        t = start + timedelta(days=day * 3, minutes=random.randint(0, 400))
        # 볼트별 검사
        for b in range(1, f["bolt_count"] + 1):
            bolt_id = f"B{b:02d}"
            t += timedelta(seconds=random.randint(20, 60))
            iso = t.replace(microsecond=0).isoformat()
            bad = random.random() < 0.12
            mm = round(random.uniform(0.5, 3.0) if bad else random.uniform(4.5, 9.0) * f["pitch_mm"] / 2.5, 1)
            vision = {"protrusion_mm": mm, "thread_count": max(0, round(mm / f["pitch_mm"])),
                      "confidence": round(random.uniform(0.75, 0.98), 2), "crop_jpg_b64": None,
                      "result": judge_protrusion(mm, f["limits"]["protrusion_mm"])}
            gp = round(random.uniform(15, 60) if bad and random.random() < .6 else random.uniform(0, 8), 1)
            mres = judge_marking(gp)
            vision["marking"] = {"gap_pct": gp, "method": "auto", "color": "red", "result": mres}
            vision["result"] = worst(vision["result"], mres)
            cond = ("체결 이상 의심" if bad and random.random() < .6
                    else "재측정 필요" if random.random() < .05 else "정상 체결")
            ref = f["tap_ref"]
            tapping = tapping_from_features(mock_features(cond, nprng), ref,
                                            f"실측 등록 n={ref['n']} ±{ref['k_sigma']}σ")
            tres = tapping["result"]
            inspections.append({
                "schema_version": SCHEMA_VERSION,
                "record_id": make_record_id(f["flange_id"], bolt_id, iso),
                "type": "BOLT", "flange_id": f["flange_id"], "bolt_id": bolt_id,
                "inspector": random.choice(PEOPLE), "device_id": "TAB-01", "inspected_at": iso,
                "vision": vision, "gap": None, "tapping": tapping,
                "final_result": worst(vision["result"], tres), "app_version": "0.1",
            })
        # 플랜지 틈 검사 1건
        t += timedelta(minutes=2)
        iso = t.replace(microsecond=0).isoformat()
        tilt = random.random() < 0.2
        gaps = [round(random.uniform(2.0, 2.4) + (random.uniform(0.6, 1.2) if tilt and k == 1 else 0), 2) for k in range(4)]
        diff, gres = judge_gap(gaps, f["limits"]["gap_mm"])
        inspections.append({
            "schema_version": SCHEMA_VERSION,
            "record_id": make_record_id(f["flange_id"], "GAP", iso),
            "type": "GAP", "flange_id": f["flange_id"], "bolt_id": "GAP",
            "inspector": random.choice(PEOPLE), "device_id": "TAB-01", "inspected_at": iso,
            "vision": None, "gap": {"gap_mm": gaps, "gap_diff_mm": diff, "result": gres}, "tapping": None,
            "final_result": gres, "app_version": "0.1",
        })

bad = [(d["flange_id"], e) for d in flanges for e in validate("flange", d)]
bad += [(d["record_id"], e) for d in inspections for e in validate("inspection", d)]
if bad:
    for who, e in bad[:20]:
        print("스키마 오류:", who, e)
    sys.exit(1)

(OUT / "fake_flanges.json").write_text(json.dumps(flanges, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "fake_inspections.json").write_text(json.dumps(inspections, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"완료: 플랜지 {len(flanges)}개, 검사 {len(inspections)}건 -> {OUT}  (스키마 검사 통과)")
