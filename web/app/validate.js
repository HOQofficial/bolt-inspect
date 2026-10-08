// 저장 전에 스키마(schema/inspection.schema.json)로 검사: 형식이 틀린 데이터는 서버에 올리지 않음.
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import inspectionSchema from "../../schema/inspection.schema.json" with { type: "json" };
import flangeSchema from "../../schema/flange.schema.json" with { type: "json" };
import { worst } from "../schema.js";

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const check = ajv.compile(inspectionSchema);
const checkRef = ajv.compile(flangeSchema.properties.tap_ref);   // 플랜지 문서 중 정상 기준(tap_ref) 부분만 검사

// tools/schema_rules.py 의 validate("inspection", doc) 와 같은 규칙 (BOLT 문서 + 타음만 있는 경우)
export function validateInspection(doc) {
  const errors = [];
  if (!check(doc)) {
    for (const e of check.errors) errors.push(`${e.instancePath || "(문서)"}: ${e.message}`);
    return errors;
  }
  if (doc.type === "BOLT") {
    if (doc.bolt_id === "GAP" || doc.gap !== null) errors.push("type=BOLT 이면 bolt_id는 Bxx, gap은 null 이어야 함");
    if (doc.vision === null && doc.tapping === null) errors.push("vision 또는 tapping 중 하나는 있어야 함");
  }
  const tp = doc.tapping;
  if (tp && tp.model === "range") {
    if (!(tp.features && tp.checks && tp.sensor_results)) errors.push("tapping.model=range 이면 features, checks, sensor_results 가 있어야 함");
    else if (tp.result !== worst(tp.sensor_results.mic, tp.sensor_results.acc)) errors.push("tapping.result 가 센서별 판정 중 가장 나쁜 값이어야 함");
  }
  const parts = [doc.vision, doc.gap, doc.tapping].map((x) => (x ? x.result : null));
  if (doc.final_result !== worst(...parts)) errors.push(`final_result 가 ${worst(...parts)} 이어야 함 (가장 나쁜 값)`);
  return errors;
}

// 정상 기준(flange.tap_ref)을 서버에 올리기 전에 검사. 오류 메시지 목록 (비어 있으면 통과)
export function validateTapRef(ref) {
  if (checkRef(ref)) return [];
  return checkRef.errors.map((e) => `${e.instancePath || "(기준)"}: ${e.message}`);
}
