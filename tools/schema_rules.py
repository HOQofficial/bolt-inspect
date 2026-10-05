"""스키마 v1.2 - JSON Schema로 표현하기 어려운 규칙과 공용 함수.

모든 팀원(앱, 대시보드, 학습 스크립트)은 이 파일의 함수를 그대로 쓰거나 똑같이 구현합니다.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_VERSION = "1.2"
KST = timezone(timedelta(hours=9))
RESULT_RANK = {"OK": 0, "CHECK": 1, "NG": 2}
# 화면에 보여줄 한글 (데이터에는 OK/CHECK/NG 로 저장)
RESULT_KO = {"OK": "정상", "CHECK": "재측정 필요", "NG": "체결 이상 의심"}
# ★ 타음 판정 규칙: 센서(음향·진동)마다 '정상 범위 밖 특징값 개수'로 판정. 숫자를 바꾸면 판정이 바뀜.
#    범위 밖 개수 < check → 정상 / check 이상 ~ ng 미만 → 재측정 필요 / ng 이상 → 체결 이상 의심
RANGE_RULE = {"check": 1, "ng": 2}
# ★ 진동(MPU6050) 임시 기본 기준: 정상 샘플이 아직 3개 미만이고 저장된 진동 기준도 없을 때만 쓰는 자리표시용 값.
#    일부러 센서가 낼 수 있는 전체 범위(20~475 Hz, ±16 g)로 넓게 잡아서 거짓 경보가 나지 않게 함 (사실상 항상 정상).
#    정상 샘플을 3개 이상 모으면 자동으로 샘플 기준으로 바뀌고, 저장하면 저장된 기준이 우선.
ACC_DEFAULT_REF = {"peak_hz": [20.0, 475.0], "mag": [0.0, 16.0], "energy_pct": [0.0, 100.0]}
FEATURE_KEYS = ("peak_hz", "mag", "energy_pct")
FEATURE_KO = {"peak_hz": "Peak Frequency", "mag": "Peak Magnitude", "energy_pct": "Band Energy"}
SENSOR_KO = {"mic": "음향 · INMP441", "acc": "진동 · MPU6050"}

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
_validators = {
    name: Draft202012Validator(json.loads((_SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")),
                               format_checker=FormatChecker())
    for name in ("flange", "inspection")
}


def now_kst_iso() -> str:
    """예: 2026-10-14T10:32:05+09:00"""
    return datetime.now(KST).replace(microsecond=0).isoformat()


def make_record_id(flange_id: str, bolt_id: str, inspected_at_iso: str) -> str:
    """FL023 + B05 + 2026-10-14T10:32:05+09:00 -> FL023-B05-20261014103205"""
    t = datetime.fromisoformat(inspected_at_iso).astimezone(KST)
    return f"{flange_id}-{bolt_id}-{t:%Y%m%d%H%M%S}"


def worst(*results):
    """None은 무시하고 가장 나쁜 판정을 돌려줌."""
    present = [r for r in results if r is not None]
    return max(present, key=RESULT_RANK.__getitem__) if present else None


def judge_gap(gap_mm, limits):
    """4지점 틈 판정. limits = flange['limits']['gap_mm']"""
    diff = round(max(gap_mm) - min(gap_mm), 2)
    if diff > limits["max_diff"] or any(g < limits["min"] or g > limits["max"] for g in gap_mm):
        result = "NG"
    elif diff > 0.75 * limits["max_diff"]:
        result = "CHECK"
    else:
        result = "OK"
    return diff, result


def judge_protrusion(mm, limits):
    """돌출 길이 판정. limits = flange['limits']['protrusion_mm']"""
    if mm < 0 or mm > limits["max"]:
        return "NG"
    if mm < limits["min"]:
        return "CHECK"
    return "OK"


MARK_LIMITS = {"ok": 10.0, "check": 20.0}   # 마킹 끊김(%) 기준. 너트 위 마킹 길이 대비


def judge_marking(gap_pct, limits=MARK_LIMITS):
    """I-마킹(풀림 표시) 판정. gap_pct = 너트 마킹과 고정부 마킹이 끊어진 거리 / 너트 마킹 길이 × 100.
    너트가 10° 정도 돌면 대략 10% 어긋남."""
    if gap_pct <= limits["ok"]:
        return "OK"
    if gap_pct <= limits["check"]:
        return "CHECK"
    return "NG"


def judge_tap_rule(peak_hz, baseline):
    """0단계 규칙 판정. baseline = flange['tap_baseline']['B05']"""
    score = abs(peak_hz - baseline["peak_hz"]) / baseline["std_hz"]
    result = "OK" if score < 3 else ("CHECK" if score < 5 else "NG")
    return round(score, 2), result


def judge_range(features, ref):
    """v1.1 범위 판정 (조원 V3 방식).
    센서(mic, acc)마다 특징값 3개 중 범위 밖 개수로 판정(기준은 위의 RANGE_RULE). 최종 = 가장 나쁜 센서.
    기준(ref)이나 측정값 중 한쪽이 없는 센서는 판정에서 빠짐(None).
    features = {"mic": {...}, "acc": {...}|None}, ref = flange["tap_ref"]
    반환: (checks, sensor_results, score=범위 밖 개수 합, result)
    """
    checks, sensor_results, out = {"mic": None, "acc": None}, {"mic": None, "acc": None}, 0
    for s in ("mic", "acc"):
        f, r = features.get(s), ref.get(s)
        if f is None or r is None:
            continue
        c = {k: bool(r[k][0] <= f[k] <= r[k][1]) for k in FEATURE_KEYS}
        n_out = 3 - sum(c.values())
        checks[s] = c
        sensor_results[s] = ("OK" if n_out < RANGE_RULE["check"]
                             else ("CHECK" if n_out < RANGE_RULE["ng"] else "NG"))
        out += n_out
    return checks, sensor_results, out, worst(sensor_results["mic"], sensor_results["acc"])


_FLOOR = {"peak_hz": lambda m: m * 0.01, "mag": lambda m: max(m * 0.03, 0.01),
          "energy_pct": lambda m: max(m * 0.03, 1.0)}  # 표준편차가 너무 작을 때 0폭 방지


def _range_from(vals, k_sigma, name):
    """특징값 dict 목록 -> {특징: [하한, 상한]} (평균 ± k×표준편차)"""
    import numpy as np
    out = {}
    for k in FEATURE_KEYS:
        v = np.array([float(x[k]) for x in vals], dtype=float)
        v = v[np.isfinite(v)]
        if len(v) == 0:
            raise ValueError(f"{name}.{k} 값이 모두 비정상(NaN)입니다. 샘플 초기화 후 다시 측정하세요.")
        mean = float(v.mean())
        sd = float(v.std(ddof=1)) if len(v) > 1 else 0.0
        w = max(k_sigma * sd, _FLOOR[k](mean))
        out[k] = [round(max(mean - w, 0.0), 4), round(mean + w, 4)]   # 특징값은 0 이상이라 하한이 음수가 되지 않게
    return out


def calc_tap_ref(samples, k_sigma):
    """정상 샘플 목록 -> tap_ref (평균 ± k×표준편차, 조원 V3의 calc_ref 와 같은 규칙).
    samples = [{"mic": {...}, "acc": {...}|None}, ...] (3개 이상)
    """
    ref = {}
    for s in ("mic", "acc"):
        vals = [x[s] for x in samples if x.get(s)]
        if not vals:
            ref[s] = None          # 이 센서 값이 하나도 없으면 기준 없음 (PC 마이크 샘플 = 진동 없음)
            continue
        if len(vals) < len(samples):   # 일부 샘플에만 있으면 조용히 빼지 말고 알림
            name = "음향" if s == "mic" else "진동"
            raise ValueError(f"{name} 값이 없는 샘플이 섞여 있어요 ({len(vals)}/{len(samples)}개만 있음). "
                             "'샘플 초기화' 후 같은 방식(ESP32)으로 처음부터 다시 모으세요.")
        ref[s] = _range_from(vals, k_sigma, s)
    return {"mic": ref["mic"], "acc": ref["acc"], "n": len(samples), "k_sigma": float(k_sigma),
            "registered_at": now_kst_iso()}


def features_from_msg(msg: dict) -> dict:
    """ESP32 메시지 v2 -> features.
    v2 예: {"v":2,"mf":3200,"mm":0.80,"me":69.0,"af":420,"am":0.71,"ae":72.0}  (af/am/ae 는 없어도 됨)
    """
    if msg.get("v") != 2:
        raise ValueError(f"특징값 메시지는 v2 여야 함: {msg}")
    mic = {"peak_hz": float(msg["mf"]), "mag": float(msg["mm"]), "energy_pct": float(msg["me"])}
    acc = ({"peak_hz": float(msg["af"]), "mag": float(msg["am"]), "energy_pct": float(msg["ae"])}
           if "af" in msg else None)
    return {"mic": mic, "acc": acc}


def tapping_from_features(features, ref, ref_source):
    """features + tap_ref -> 스키마의 tapping 객체 (model='range')"""
    checks, sres, score, result = judge_range(features, ref)
    return {"peak_hz": round(features["mic"]["peak_hz"], 1), "decay_ms": None, "score": score,
            "model": "range", "result": result, "features": features, "checks": checks,
            "sensor_results": sres, "ref_source": ref_source}


def validate(kind: str, doc: dict) -> list:
    """kind = 'flange' 또는 'inspection'. 오류 메시지 리스트를 돌려줌(비어 있으면 통과)."""
    errors = [f"{'/'.join(map(str, e.path)) or '(문서)'}: {e.message}"
              for e in _validators[kind].iter_errors(doc)]
    if kind == "inspection" and not errors:
        if doc["type"] == "BOLT":
            if doc["bolt_id"] == "GAP" or doc["gap"] is not None:
                errors.append("type=BOLT 이면 bolt_id는 Bxx, gap은 null 이어야 함")
            if doc["vision"] is None and doc["tapping"] is None:
                errors.append("type=BOLT 이면 vision 또는 tapping 중 하나는 있어야 함")
        else:  # GAP
            if doc["bolt_id"] != "GAP" or doc["gap"] is None or doc["vision"] or doc["tapping"]:
                errors.append("type=GAP 이면 bolt_id=GAP, gap 필수, vision/tapping 은 null")
        if doc["gap"] is not None:
            expect = round(max(doc["gap"]["gap_mm"]) - min(doc["gap"]["gap_mm"]), 2)
            if abs(expect - doc["gap"]["gap_diff_mm"]) > 0.011:
                errors.append(f"gap_diff_mm 이 {expect} 이어야 함")
        expect_id = make_record_id(doc["flange_id"], doc["bolt_id"], doc["inspected_at"])
        if doc["record_id"] != expect_id:
            errors.append(f"record_id 가 {expect_id} 이어야 함")
        tp = doc["tapping"]
        if tp is not None and tp["model"] == "range":
            if not (tp.get("features") and tp.get("checks") and tp.get("sensor_results")):
                errors.append("tapping.model=range 이면 features, checks, sensor_results 가 있어야 함")
            elif tp["result"] != worst(tp["sensor_results"]["mic"], tp["sensor_results"]["acc"]):
                errors.append("tapping.result 가 센서별 판정 중 가장 나쁜 값이어야 함")
        parts = [(doc[k] or {}).get("result") for k in ("vision", "gap", "tapping")]
        if doc["final_result"] != worst(*parts):
            errors.append(f"final_result 가 {worst(*parts)} 이어야 함 (가장 나쁜 값)")
    return errors
