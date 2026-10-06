"""local_db(내 PC) <-> Firestore(서버) 옮기기 / 지우기 도구.

사용법 (프로젝트 폴더에서, 가상환경을 켠 상태로):
  python tools/local_firestore_tool.py up        local_db 의 플랜지·기록을 Firestore 로 올림 (local_db 는 그대로 남음)
  python tools/local_firestore_tool.py up --real 가짜 시험 데이터(sample/fake_*.json 에 있는 것)는 빼고 내가 만든 것만 올림
  python tools/local_firestore_tool.py wipe      Firestore 의 플랜지·기록을 전부 지움 (local_db 는 건드리지 않음)

올리기는 같은 ID 면 덮어쓰기라서 여러 번 해도 중복되지 않아요. 지우기 전에는 '삭제' 를 직접 입력해야 해요.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
import store  # noqa: E402

KEYS = {"flanges": "flange_id", "inspections": "record_id"}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _fake_ids(name):
    return {d[KEYS[name]] for d in _load(ROOT / "sample" / f"fake_{name}.json")}


def up(real_only):
    if not store.KEY.exists():
        sys.exit("key.json 이 없어요. 프로젝트 폴더에 key.json 을 먼저 넣어 주세요.")
    db = store._db()
    for name, idk in KEYS.items():
        docs = _load(store.LOCAL / f"{name}.json")
        if real_only:
            fake = _fake_ids(name)
            docs = [d for d in docs if d[idk] not in fake]
        kind = "flange" if name == "flanges" else "inspection"
        bad = 0
        batch, n = db.batch(), 0
        for d in docs:
            errs = store.validate(kind, d)
            if errs:
                bad += 1
                print(f"  건너뜀 {d.get(idk)}: {errs[0]}")
                continue
            batch.set(db.collection(name).document(d[idk]), d)
            n += 1
            if n % 400 == 0:
                batch.commit(); batch = db.batch()
        batch.commit()
        print(f"{name}: {n}개 올림" + (f" (형식 오류로 건너뜀 {bad}개)" if bad else ""))


def wipe():
    if not store.KEY.exists():
        sys.exit("key.json 이 없어요.")
    db = store._db()
    counts = {n: sum(1 for _ in db.collection(n).stream()) for n in KEYS}
    print(f"Firestore 에 있는 것: 플랜지 {counts['flanges']}개, 검사 기록 {counts['inspections']}개")
    if input("전부 지우려면 '삭제' 라고 입력하세요 (취소는 그냥 엔터): ").strip() != "삭제":
        sys.exit("취소했어요. 아무것도 지우지 않았어요.")
    for name in KEYS:
        docs = list(db.collection(name).stream())
        for i in range(0, len(docs), 400):
            b = db.batch()
            for d in docs[i:i + 400]:
                b.delete(d.reference)
            b.commit()
        print(f"{name}: {len(docs)}개 지움")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["up"]:
        up("--real" in a)
    elif a[:1] == ["wipe"]:
        wipe()
    else:
        print(__doc__)
