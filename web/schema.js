// 스키마 v1.1 - 웹앱(태블릿)에서 쓰는 공용 상수와 함수.
// tools/schema_rules.py 와 똑같이 동작해야 합니다. 한쪽을 바꾸면 반드시 다른 쪽도 바꾸세요.

export const SCHEMA_VERSION = "1.2";
export const APP_VERSION = "0.1";
export const RESULT_RANK = { OK: 0, CHECK: 1, NG: 2 };

// 한국시간 ISO 문자열: 2026-10-14T10:32:05+09:00
export function nowKstIso() {
  const k = new Date(Date.now() + 9 * 3600 * 1000);
  return k.toISOString().slice(0, 19) + "+09:00";
}

// FL023 + B05 + "2026-10-14T10:32:05+09:00" -> FL023-B05-20261014103205
export function makeRecordId(flangeId, boltId, kstIso) {
  return `${flangeId}-${boltId}-${kstIso.slice(0, 19).replace(/[-:T]/g, "")}`;
}

export function worst(...results) {
  const r = results.filter(Boolean);
  return r.length ? r.reduce((a, b) => (RESULT_RANK[b] > RESULT_RANK[a] ? b : a)) : null;
}

// 볼트 검사 1건을 스키마 모양 그대로 만들기
export function newBoltRecord({ flangeId, boltId, inspector, deviceId, vision = null, tapping = null }) {
  const at = nowKstIso();
  return {
    schema_version: SCHEMA_VERSION,
    record_id: makeRecordId(flangeId, boltId, at),
    type: "BOLT", flange_id: flangeId, bolt_id: boltId,
    inspector, device_id: deviceId, inspected_at: at,
    vision, gap: null, tapping,
    final_result: worst(vision?.result, tapping?.result),
    app_version: APP_VERSION,
  };
}

// ESP32 BLE 메시지 v1 -> tapping 객체
// 예: {"v":1,"pk":3105,"dc":18.2,"sc":0.38,"m":"rule","r":"OK"}
export function tappingFromBle(msg) {
  if (msg.v !== 1) throw new Error("모르는 BLE 메시지 버전: " + msg.v);
  return { peak_hz: msg.pk, decay_ms: msg.dc ?? null, score: msg.sc, model: msg.m, result: msg.r };
}

// ESP32 특징값 메시지 v2 -> features (스키마 v1.1, tools/schema_rules.py 의 features_from_msg 와 같음)
// 예: {"v":2,"mf":3200,"mm":0.80,"me":69.0,"af":420,"am":0.71,"ae":72.0}  (af/am/ae 는 없어도 됨)
export function featuresFromBle(msg) {
  if (msg.v !== 2) throw new Error("특징값 메시지는 v2 여야 함");
  const mic = { peak_hz: msg.mf, mag: msg.mm, energy_pct: msg.me };
  const acc = "af" in msg ? { peak_hz: msg.af, mag: msg.am, energy_pct: msg.ae } : null;
  return { mic, acc };
}

// 범위 판정 (tools/schema_rules.py 의 judge_range 와 같음). ref = flange.tap_ref
export function judgeRange(features, ref) {
  const keys = ["peak_hz", "mag", "energy_pct"];
  const checks = { mic: null, acc: null }, sensor_results = { mic: null, acc: null };
  let out = 0;
  for (const s of ["mic", "acc"]) {
    const f = features[s], r = ref[s];
    if (!f || !r) continue;
    checks[s] = Object.fromEntries(keys.map((k) => [k, r[k][0] <= f[k] && f[k] <= r[k][1]]));
    const n = keys.filter((k) => !checks[s][k]).length;
    sensor_results[s] = n === 0 ? "OK" : n === 1 ? "CHECK" : "NG";
    out += n;
  }
  return { checks, sensor_results, score: out, result: worst(sensor_results.mic, sensor_results.acc) };
}
