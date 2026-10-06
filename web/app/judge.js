// 판정 + 기록 만들기. 규칙은 web/schema.js (= tools/schema_rules.py 와 같은 규칙)를 그대로 씀.
import { judgeRange, worst, makeRecordId, SCHEMA_VERSION } from "../schema.js";

export const APP_VERSION = "1.0";
export const RESULT_KO = { OK: "정상", CHECK: "재측정 필요", NG: "체결 이상 의심" };
export const RESULT_COLOR = { OK: "#15803d", CHECK: "#b45309", NG: "#b91c1c" };

// 대시보드(tapping.py)와 같은 글자: 예) 실측 등록 n=10 ±3σ
export function refSourceText(ref) {
  return `실측 등록 n=${ref.n} ±${ref.k_sigma}σ`;
}

// 특징값 + 정상 기준 -> 스키마의 tapping 객체 (tools/schema_rules.py 의 tapping_from_features 와 같음)
// 기준이 없어서 판정할 센서가 하나도 없으면 null
export function tappingFromFeatures(features, ref, refSource) {
  const j = judgeRange(features, ref);
  if (!j.result) return null;
  return {
    peak_hz: Math.round(features.mic.peak_hz * 10) / 10,
    decay_ms: null,
    score: j.score,
    model: "range",
    result: j.result,
    features,
    checks: j.checks,
    sensor_results: j.sensor_results,
    ref_source: refSource,
  };
}

export function kstIso(ms) {
  return new Date(ms + 9 * 3600 * 1000).toISOString().slice(0, 19) + "+09:00";
}

// 타음 검사 1건을 스키마 v1.2 모양으로 만들기. 같은 볼트를 같은 초에 두 번 저장해도 덮어쓰지 않게 id 를 1초씩 미룸.
export function makeRecord({ flangeId, boltId, inspector, deviceId, tapping, note = null, nowMs = Date.now(), isTaken = () => false }) {
  let ms = nowMs, at = kstIso(ms), id = makeRecordId(flangeId, boltId, at);
  while (isTaken(id)) { ms += 1000; at = kstIso(ms); id = makeRecordId(flangeId, boltId, at); }
  const rec = {
    schema_version: SCHEMA_VERSION,
    record_id: id,
    type: "BOLT",
    flange_id: flangeId,
    bolt_id: boltId,
    inspector,
    device_id: deviceId,
    inspected_at: at,
    vision: null,
    gap: null,
    tapping,
    final_result: worst(tapping.result),
    app_version: APP_VERSION,
  };
  if (note) rec.note = String(note).slice(0, 200);
  return rec;
}
