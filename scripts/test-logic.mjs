// 블루투스 조각 이어 붙이기, 판정, 기록 만들기, 스키마 검사를 확인한다. 사용: npm test
import { readFileSync, writeFileSync } from "node:fs";
import assert from "node:assert/strict";
import { LineAssembler } from "../web/app/lines.js";
import { featuresFromBle } from "../web/schema.js";
import { tappingFromFeatures, refSourceText, makeRecord } from "../web/app/judge.js";
import { validateInspection } from "../web/app/validate.js";

let n = 0;
const ok = (name, fn) => { fn(); n++; console.log("  ✔", name); };
const flanges = JSON.parse(readFileSync(new URL("../sample/fake_flanges.json", import.meta.url), "utf8"));
const fl = flanges[0];
const mid = (r) => (r[0] + r[1]) / 2;
const msgAt = (ref, over = {}) => ({ v: 2, seq: 1, src: "mic",
  mf: mid(ref.mic.peak_hz), mm: mid(ref.mic.mag), me: mid(ref.mic.energy_pct),
  af: mid(ref.acc.peak_hz), am: mid(ref.acc.mag), ae: mid(ref.acc.energy_pct), ...over });
const judge = (msg, ref = fl.tap_ref) => tappingFromFeatures(featuresFromBle(msg), ref, refSourceText(ref));
const dump = [];

console.log("블루투스 조각");
ok("20바이트씩 쪼갠 메시지 2개가 정확히 2줄로 이어 붙음", () => {
  const lines = [];
  const asm = new LineAssembler((l) => lines.push(l));
  const text = JSON.stringify(msgAt(fl.tap_ref)) + "\n" + JSON.stringify(msgAt(fl.tap_ref, { seq: 2 })) + "\n";
  const bytes = new TextEncoder().encode(text);
  for (let i = 0; i < bytes.length; i += 20) asm.push(bytes.slice(i, i + 20));
  assert.equal(lines.length, 2); assert.equal(JSON.parse(lines[1]).seq, 2);
});
ok("줄바꿈 없이 이어지는 쓰레기는 버퍼가 무한히 커지지 않음", () => {
  const asm = new LineAssembler(() => {});
  for (let i = 0; i < 100; i++) asm.push(new TextEncoder().encode("x".repeat(20)));
  assert.ok(asm.buf.length <= 600);
});

console.log("판정");
ok("기준 중앙값 → 정상", () => assert.equal(judge(msgAt(fl.tap_ref)).result, "OK"));
ok("음향 1개 이탈 → 재측정", () => assert.equal(judge(msgAt(fl.tap_ref, { mf: 9999 })).result, "CHECK"));
ok("음향 2개 이탈 → 이상", () => assert.equal(judge(msgAt(fl.tap_ref, { mf: 9999, mm: 0.01 })).result, "NG"));
ok("진동만 이상해도 종합이 나빠짐", () => {
  const t = judge(msgAt(fl.tap_ref, { af: 100, am: 9, ae: 1 }));
  assert.equal(t.sensor_results.mic, "OK"); assert.equal(t.sensor_results.acc, "NG"); assert.equal(t.result, "NG");
});
ok("진동 값이 안 오면 음향만으로 판정 (acc=null)", () => {
  const { af, am, ae, ...m } = msgAt(fl.tap_ref);
  const t = judge(m); assert.equal(t.features.acc, null); assert.equal(t.sensor_results.acc, null); assert.equal(t.result, "OK");
});
ok("기준에 진동이 없으면 진동은 판정에서 빠짐", () => {
  const ref = { ...fl.tap_ref, acc: null };
  const t = judge(msgAt(fl.tap_ref), ref); assert.equal(t.sensor_results.acc, null); assert.equal(t.result, "OK");
});
ok("기준에 판정할 센서가 하나도 없으면 null", () => assert.equal(judge(msgAt(fl.tap_ref), { ...fl.tap_ref, mic: null, acc: null }), null));
ok("v1 메시지는 거부", () => assert.throws(() => featuresFromBle({ v: 1 })));

console.log("기록 + 스키마 검사");
for (const [name, over] of [["정상", {}], ["재측정", { mf: 9999 }], ["이상", { mf: 9999, mm: 0.01 }]]) {
  ok(`${name} 기록이 스키마를 통과`, () => {
    const rec = makeRecord({ flangeId: fl.flange_id, boltId: "B02", inspector: "홍길동", deviceId: "TAB-01",
      tapping: judge(msgAt(fl.tap_ref, over)), nowMs: Date.UTC(2026, 9, 6, 1, 2, 3) });
    assert.deepEqual(validateInspection(rec), []);
    assert.equal(rec.record_id, `${fl.flange_id}-B02-20261006100203`);   // 한국시간 10:02:03
    dump.push(rec);
  });
}
ok("같은 초에 두 번 저장하면 id 가 1초 뒤로 밀림", () => {
  const taken = new Set([`${fl.flange_id}-B01-20261006100203`]);
  const rec = makeRecord({ flangeId: fl.flange_id, boltId: "B01", inspector: "a", deviceId: "d", tapping: judge(msgAt(fl.tap_ref)),
    nowMs: Date.UTC(2026, 9, 6, 1, 2, 3), isTaken: (id) => taken.has(id) });
  assert.equal(rec.record_id, `${fl.flange_id}-B01-20261006100204`);
});
ok("검사자 이름이 비면 스키마가 거부", () => {
  const rec = makeRecord({ flangeId: fl.flange_id, boltId: "B01", inspector: "", deviceId: "d", tapping: judge(msgAt(fl.tap_ref)) });
  assert.ok(validateInspection(rec).length > 0);
});
ok("최종 판정을 일부러 틀리게 하면 거부", () => {
  const rec = makeRecord({ flangeId: fl.flange_id, boltId: "B01", inspector: "a", deviceId: "d", tapping: judge(msgAt(fl.tap_ref, { mf: 9999 })) });
  rec.final_result = "OK";
  assert.ok(validateInspection(rec).length > 0);
});

if (process.env.DUMP) writeFileSync(process.env.DUMP, JSON.stringify(dump));
console.log(`\n${n}개 확인 통과`);
