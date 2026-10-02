"""가짜 데이터를 Firestore에 올립니다 (3단계에서 Firebase 연결 확인용).

준비: 프로젝트 맨 위 폴더에 key.json (Firebase 서비스 계정 키)이 있어야 합니다.
실행:  python tools/seed_firestore.py          -> 올리기
       python tools/seed_firestore.py --clear  -> 가짜 데이터 지우기 (app_version 0.1 인 검사 + 가짜 플랜지)
"""
import json
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_rules import validate

ROOT = Path(__file__).resolve().parent.parent
KEY = ROOT / "key.json"
if not KEY.exists():
    sys.exit("key.json 이 없습니다. 가이드 3단계의 '서비스 계정 키' 부분을 먼저 하세요.")

firebase_admin.initialize_app(credentials.Certificate(str(KEY)))
db = firestore.client()
flanges = json.loads((ROOT / "sample/fake_flanges.json").read_text(encoding="utf-8"))
inspections = json.loads((ROOT / "sample/fake_inspections.json").read_text(encoding="utf-8"))

if "--clear" in sys.argv:
    n = 0
    for d in db.collection("inspections").where("app_version", "==", "0.1").stream():
        d.reference.delete(); n += 1
    for f in flanges:
        db.collection("flanges").document(f["flange_id"]).delete()
    print(f"삭제 완료: 검사 {n}건, 플랜지 {len(flanges)}개")
    sys.exit(0)

batch, count = db.batch(), 0
for kind, coll, docs, key in (("flange", "flanges", flanges, "flange_id"),
                              ("inspection", "inspections", inspections, "record_id")):
    for d in docs:
        errs = validate(kind, d)
        if errs:
            sys.exit(f"{d[key]} 스키마 오류: {errs}")
        batch.set(db.collection(coll).document(d[key]), d)  # 문서 ID = flange_id / record_id
        count += 1
        if count % 400 == 0:  # Firestore 배치는 최대 500건
            batch.commit(); batch = db.batch()
batch.commit()
print(f"업로드 완료: 플랜지 {len(flanges)}개, 검사 {len(inspections)}건")
