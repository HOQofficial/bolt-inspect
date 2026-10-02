"""데이터 저장소 - key.json 이 있으면 Firestore, 없으면 local_db/ 폴더의 JSON 파일.

화면 코드는 저장소 종류를 신경 쓰지 않고 이 파일의 함수만 부릅니다.
저장 전에 항상 스키마 검사를 하므로, 형식이 틀린 데이터는 들어가지 않습니다.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from schema_rules import validate  # noqa: E402

KEY = ROOT / "key.json"
LOCAL = ROOT / "local_db"


class SchemaError(ValueError):
    pass


def _check(kind, doc):
    errs = validate(kind, doc)
    if errs:
        raise SchemaError("; ".join(errs))


# ---------------- Firestore ----------------
def _db():
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(KEY)))
    return firestore.client()


# ---------------- 로컬 JSON ----------------
def _local(name):
    LOCAL.mkdir(exist_ok=True)
    p = LOCAL / f"{name}.json"
    if not p.exists():  # 처음 실행 시 가짜 데이터로 시작
        shutil.copy(ROOT / "sample" / f"fake_{name}.json", p)
    return p


def _read(name):
    return json.loads(_local(name).read_text(encoding="utf-8"))


def _write(name, docs):
    _local(name).write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------- 공개 함수 ----------------
def source_name():
    return "Firestore (실데이터)" if KEY.exists() else "내 PC local_db/ (key.json 없음)"


def list_flanges():
    if KEY.exists():
        return [d.to_dict() for d in _db().collection("flanges").stream()]
    return _read("flanges")


def list_inspections():
    if KEY.exists():
        return [d.to_dict() for d in _db().collection("inspections").stream()]
    return _read("inspections")


def save_inspection(doc):
    _check("inspection", doc)
    if KEY.exists():
        _db().collection("inspections").document(doc["record_id"]).set(doc)
    else:
        docs = [d for d in _read("inspections") if d["record_id"] != doc["record_id"]]
        _write("inspections", docs + [doc])


def save_flange(doc):
    _check("flange", doc)
    if KEY.exists():
        _db().collection("flanges").document(doc["flange_id"]).set(doc)
    else:
        docs = [d for d in _read("flanges") if d["flange_id"] != doc["flange_id"]]
        _write("flanges", docs + [doc])
