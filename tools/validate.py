"""JSON 파일이 스키마 v1.0을 지키는지 검사합니다.

실행 예:
  python tools/validate.py inspection sample/fake_inspections.json
  python tools/validate.py flange sample/fake_flanges.json
파일 안에는 문서 1개(객체) 또는 여러 개(배열)가 들어 있으면 됩니다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_rules import validate

if len(sys.argv) != 3 or sys.argv[1] not in ("flange", "inspection"):
    print(__doc__)
    sys.exit(2)

kind, path = sys.argv[1], Path(sys.argv[2])
data = json.loads(path.read_text(encoding="utf-8"))
docs = data if isinstance(data, list) else [data]
fails = 0
for i, d in enumerate(docs):
    errs = validate(kind, d)
    if errs:
        fails += 1
        name = d.get("record_id") or d.get("flange_id") or f"#{i}"
        for e in errs:
            print(f"[X] {name}  {e}")
print(f"{len(docs)}개 중 {len(docs) - fails}개 통과" + ("" if fails else "  모두 OK"))
sys.exit(1 if fails else 0)
