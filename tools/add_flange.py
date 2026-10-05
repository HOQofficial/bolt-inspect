"""시편(또는 실제 플랜지)을 앱에 등록/수정합니다.

예) 1단계 합판 시편, 너트 높이는 캘리퍼로 잰 값:
  python tools/add_flange.py --id FL101 --zone 시편-합판 --nut-height 13.0
예) 2단계 쇠 플랜지 시편:
  python tools/add_flange.py --id FL102 --zone 시편-쇠플랜지 --nut-height 13.0

key.json 이 있으면 Firestore, 없으면 local_db/ 에 저장 (앱과 같은 곳).
이미 있는 ID 면 값만 바꾸고, 타음 기준(tap_ref, tap_baseline)은 그대로 둡니다.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "dashboard")]
import store  # noqa: E402
from schema_rules import SCHEMA_VERSION, now_kst_iso  # noqa: E402

PITCH = {"M12": 1.75, "M16": 2.0, "M20": 2.5, "M24": 3.0, "M30": 3.5, "M36": 4.0}

ap = argparse.ArgumentParser(description="플랜지(시편) 등록")
ap.add_argument("--id", required=True, help="FL101 처럼 FL + 숫자 3자리")
ap.add_argument("--zone", default="시편", help="위치/이름. 예: 시편-합판")
ap.add_argument("--spec", default="M16", choices=list(PITCH))
ap.add_argument("--count", type=int, default=4, help="볼트 개수")
ap.add_argument("--nut-height", type=float, required=True, help="너트 높이 mm (캘리퍼로 잰 값)")
ap.add_argument("--pitch", type=float, help="나사 피치 mm (안 쓰면 규격 기본값)")
ap.add_argument("--prot", type=float, nargs=2, metavar=("MIN", "MAX"), help="돌출 허용 mm (기본: 피치×2 ~ 피치×8)")
ap.add_argument("--gap", type=float, nargs=3, metavar=("MIN", "MAX", "DIFF"), default=[1.5, 3.5, 0.8],
                help="틈 허용 최소·최대·4지점 편차 mm")
a = ap.parse_args()

pitch = a.pitch or PITCH[a.spec]
pmin, pmax = a.prot or (2 * pitch, 8 * pitch)
old = {f["flange_id"]: f for f in store.list_flanges()}.get(a.id, {})
doc = {
    "schema_version": SCHEMA_VERSION, "flange_id": a.id, "zone": a.zone, "bolt_spec": a.spec,
    "bolt_count": a.count, "nut_height_mm": a.nut_height, "pitch_mm": pitch,
    "limits": {"protrusion_mm": {"min": pmin, "max": pmax},
               "gap_mm": {"min": a.gap[0], "max": a.gap[1], "max_diff": a.gap[2]}},
    "tap_baseline": old.get("tap_baseline", {}), "updated_at": now_kst_iso(),
    "tap_ref": old.get("tap_ref"),
}
store.save_flange(doc)
print(f"{'수정' if old else '등록'} 완료: {a.id} ({a.zone}) {a.spec} × {a.count}, 너트 높이 {a.nut_height} mm, "
      f"돌출 {pmin}~{pmax} mm, 틈 {a.gap[0]}~{a.gap[1]} mm (편차 {a.gap[2]}) -> {store.source_name()}")
