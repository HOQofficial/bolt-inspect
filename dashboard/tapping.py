"""타음 검사 - 조원 V3 화면을 스키마 v1.1 에 맞게 옮긴 것.

측정 -> 특징값 6개 -> 기준 범위 비교 -> 큰 판정 표시 -> 저장(Firestore 또는 local_db)
정상 기준은 플랜지마다 등록되어 저장됩니다(flanges.tap_ref).
"""
import csv
import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import store
import ui
from schema_rules import (ACC_DEFAULT_REF, FEATURE_KO, RANGE_RULE, SCHEMA_VERSION, calc_tap_ref, features_from_msg,
                          make_record_id, now_kst_iso, spectrum_from_msg, tapping_from_features)
from sim import CONDITIONS, DEMO_REF, mock_features

APP_VERSION = "1.1"

# 정상 샘플 원본 기록: '➕ 정상 샘플로 추가'를 누를 때마다 한 줄씩 쌓임 (나중에 학습·발표 자료에 사용)
SAMPLE_CSV = Path(__file__).resolve().parent.parent / "data" / "tap_samples.csv"
SAMPLE_COLS = ["recorded_at", "session", "flange_id", "bolt_id", "state", "torque_pct", "hit_no", "recorded_by",
               "device_id", "record_id", "mic_peak_hz", "mic_mag", "mic_energy_pct",
               "acc_peak_hz", "acc_mag", "acc_energy_pct"]


def log_sample(res, inspector_name, state="normal", torque_pct=100):
    """정상 샘플 1건을 data/tap_samples.csv 에 한 줄 추가. 돌려주는 값 = 같은 볼트·같은 날 몇 번째인지(hit_no).
    파일이 엑셀로 열려 있으면 쓸 수 없으므로 OSError 가 날 수 있음(호출하는 쪽에서 처리)."""
    doc, ft = res["doc"], res["features"]
    at = now_kst_iso()
    session = at[:10].replace("-", "")            # 날짜 = 세션 (다른 날 데이터로 시험용을 나누기 위함)
    hit_no = 1
    if SAMPLE_CSV.exists():
        with SAMPLE_CSV.open(encoding="utf-8-sig", newline="") as fh:
            hit_no += sum(1 for row in csv.DictReader(fh)
                          if (row.get("flange_id"), row.get("bolt_id"), row.get("session"), row.get("state"))
                          == (doc["flange_id"], doc["bolt_id"], session, state))
    row = {"recorded_at": at, "session": session, "flange_id": doc["flange_id"], "bolt_id": doc["bolt_id"],
           "state": state, "torque_pct": torque_pct, "hit_no": hit_no, "recorded_by": inspector_name or "미입력",
           "device_id": doc.get("device_id", ""), "record_id": doc.get("record_id", "")}
    for sn in ("mic", "acc"):
        v = ft.get(sn)
        for k in ("peak_hz", "mag", "energy_pct"):
            row[f"{sn}_{k}"] = "" if v is None else v[k]
    SAMPLE_CSV.parent.mkdir(exist_ok=True)
    new_file = not SAMPLE_CSV.exists()
    with SAMPLE_CSV.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as fh:   # utf-8-sig = 엑셀에서 한글 안 깨짐
        w = csv.DictWriter(fh, fieldnames=SAMPLE_COLS)
        if new_file:
            w.writeheader()
        w.writerow(row)
    return hit_no

def csv_record_ids():
    """data/tap_samples.csv 에 이미 들어간 측정의 record_id 모음 (프로그램을 껐다 켜도 같은 측정을 또 넣지 않기 위함)"""
    if not SAMPLE_CSV.exists():
        return set()
    try:
        with SAMPLE_CSV.open(encoding="utf-8-sig", newline="") as fh:
            return {row.get("record_id") for row in csv.DictReader(fh) if row.get("record_id")}
    except OSError:
        return set()


def already_added(res):
    """이 측정이 이미 정상 샘플로 들어갔는지. 측정마다 고유한 key(ESP32 의 bootId-seq 또는 기록 ID)로 구분"""
    return (res.get("key") or res["doc"]["record_id"]) in ss.sample_keys or res["doc"]["record_id"] in csv_record_ids()


def add_sample(res, inspector_name):
    """정상 샘플 추가. 돌려주는 값 = (추가됐는지, 알림 글자)"""
    if already_added(res):
        return False, "이미 정상 샘플로 추가한 측정이에요. (같은 측정은 한 번만 들어가요)"
    mic = res["features"].get("mic")
    if mic and mic["mag"] >= 0.98:
        return False, "소리가 너무 커서 잘린 측정(Peak Magnitude ≈ 1)이라 정상 샘플로 넣을 수 없어요."
    if ss.samples and bool(ss.samples[0].get("acc")) != bool(res["features"].get("acc")):
        return False, "앞서 모은 샘플과 센서 구성이 달라요(진동 값 유무). '샘플 초기화' 후 같은 방식으로 다시 모으세요."
    ss.samples.append(res["features"])
    ss.sample_keys.add(res.get("key") or res["doc"]["record_id"])
    try:
        n_hit = log_sample(res, inspector_name)
        return True, f"정상 샘플 {len(ss.samples)}개째 추가 · data/tap_samples.csv 에 기록 ({n_hit}번째)"
    except OSError as e:   # 엑셀로 열어 둔 경우 등: 화면 기준 계산은 계속, 기록만 실패
        return True, f"정상 샘플 {len(ss.samples)}개째 추가됨. 그런데 CSV 기록은 실패: {e}"


ss = st.session_state
for k, v in {"result": None, "samples": [], "count": 0, "last_saved": None, "phone_seen": None,
             "sample_keys": set(), "phone_recent": []}.items():
    ss.setdefault(k, v)
PHONE = "폰·태블릿"
PC_DEVICES = {"TAP-USB", "PC-SIM"}   # 이 화면이 직접 측정해 저장한 기록의 기기 이름
if ss.get("pending_sel"):   # 폰에서 측정한 플랜지·볼트로 선택을 맞춤 (위젯을 그리기 전에 바꿔야 함)
    ss.sel_fid, ss.sel_bolt = ss.pop("pending_sel")


@st.cache_data(ttl=15)
def flanges():
    return {f["flange_id"]: f for f in store.list_flanges()}


def read_serial(port, cmd="S", timeout=12):
    """ESP32 에 USB 로 명령을 보내고(S = 솔레노이드 타격 + 측정, M = 손으로 칠 때 8초 대기) 특징값 메시지 v2 한 줄을 기다림.
    돌려주는 값 = (features, spectrum, 측정 고유키). 포트를 매번 열면 ESP32 가 재부팅되므로 한 번 연 포트를 계속 씀."""
    import serial
    if ss.get("ser_port") != port:
        if ss.get("ser"):
            ss.ser.close()
        try:
            ss.ser = serial.Serial(port, 115200, timeout=1)
        except serial.SerialException as e:
            ss.ser, ss.ser_port = None, None
            raise ValueError(f"{port} 를 열 수 없어요. Arduino IDE 시리얼 모니터가 켜져 있으면 닫고 다시 하세요. ({e})")
        ss.ser_port = port
        time.sleep(2)  # 열 때 보드가 재시작하는 시간
    ss.ser.reset_input_buffer()
    ss.ser.write(f"{cmd}\n".encode())
    end = time.time() + timeout
    while time.time() < end:
        line = ss.ser.readline().decode("utf-8", "ignore").strip()
        if line.startswith("{"):
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("evt") == "miss":
                raise TimeoutError("ESP32 가 소리를 듣지 못했어요. 마이크 위치와 솔레노이드 타격(전원·배선)을 확인하세요.")
            if msg.get("v") == 2 and "mf" in msg:
                return features_from_msg(msg), spectrum_from_msg(msg), msg.get("k")
    raise TimeoutError(f"{timeout}초 안에 ESP32 응답이 없어요. 올바른 펌웨어(tap_sensor_v2)를 올렸는지, "
                       "시리얼 모니터가 닫혀 있는지, 포트가 맞는지 확인하세요.")


FL = flanges()
if not FL:
    st.error("등록된 플랜지가 없습니다. python tools/seed_firestore.py 로 가짜 플랜지를 먼저 올리세요.")
    st.stop()

# ---------------- 사이드바: 검사 설정 + 정상 기준 등록 ----------------
with st.sidebar:
    st.header("검사 설정")
    fid = st.selectbox("플랜지", sorted(FL), key="sel_fid")
    f = FL[fid]
    bolt = st.selectbox("볼트 (12시부터 시계방향)", [f"B{i:02d}" for i in range(1, f["bolt_count"] + 1)],
                        key="sel_bolt")
    inspector = st.text_input("검사자", value=ss.get("inspector", "홍길동"), key="inspector")
    source = st.radio("측정 방식", ["가상 데이터", "ESP32 (USB)", PHONE], horizontal=True,
                      help="폰·태블릿 = 블루투스로 측정한 결과를 실시간으로 받아 봄 (주 사용 방식)")
    if source == "가상 데이터":
        cond = st.selectbox("가상 측정 조건", CONDITIONS)
    elif source == PHONE:
        phone_every = st.select_slider("폰 측정 확인 간격(초)", [3, 5, 10], value=5,
                                       help="한 번에 1건만 읽어서 읽기 한도(하루 5만)는 거의 안 써요.")
        st.caption("폰·태블릿 앱의 '측정' 탭에서 측정하면 이 화면에 자동으로 나타나요. 폰 앱의 '측정되면 자동 저장'이 켜져 있어야 하고, "
                   "폰은 ESP32 와 블루투스로 연결돼 있어야 해요. 이 화면을 연 뒤에 새로 측정한 것부터 보여요. "
                   "(저장소가 Firestore 일 때만 폰 기록이 와요) 폰의 '기준 등록' 탭에서 모은 샘플은 서버로 오지 않아요 → "
                   "여기서 등록하려면 폰 '측정' 탭의 결과를 아래 '정상 샘플로 추가'로 넣으세요.")
    else:
        try:
            from serial.tools import list_ports
            ports = [(p.device, f"{p.device} - {p.description}") for p in list_ports.comports()]
        except Exception:
            ports = []
        if st.button("🔄 포트 다시 찾기", help="ESP32 를 앱을 켠 뒤에 꽂았을 때"):
            st.rerun()
        if ports:
            port = st.selectbox("COM 포트", [p for p, _ in ports], format_func=dict(ports).get,
                                help="ESP32 는 보통 'CP210x' 또는 'CH340' 이 이름에 들어 있어요")
        else:
            st.warning("USB 로 연결된 장치가 안 보여요. 케이블(데이터용인지)과 드라이버를 확인하세요.")
            port = st.text_input("COM 포트 (직접 입력)", "COM3")
        usb_cmd = "S" if st.radio("치는 방법", ["솔레노이드가 치기", "손으로 치기"], horizontal=True,
                                  help="솔레노이드 = ESP32 가 한 번 치고 그 소리만 측정 / 손 = 누른 뒤 8초 안에 직접 치기") == "솔레노이드가 치기" else "M"
        st.caption("Arduino IDE 의 시리얼 모니터는 꼭 닫으세요 (포트를 한 프로그램만 쓸 수 있어요). "
                   "▶ 측정 시작을 누르면 ESP32 에 명령이 가고 한 번만 측정해요.")
    if source == "ESP32 (USB)":
        led_on = st.toggle("판정 LED 켜기 (ESP32)", value=True,
                           help="측정 결과에 따라 ESP32 에 연결한 초록(정상)·빨강(재측정 깜빡임 / 이상 켜짐) LED 를 켭니다")
    autosave = st.toggle("측정하면 자동 저장", value=True)

    st.divider()
    st.subheader("정상 기준 등록")
    st.caption(f"{fid} 에 저장됩니다. 정상 체결 볼트를 여러 번 측정한 뒤 등록하세요.")
    target_n = st.number_input("기준 측정 목표 횟수", 3, 100, 10)
    k_sigma = st.select_slider("기준 범위 폭 (평균 ± k×표준편차)", [1.0, 1.5, 2.0, 2.5, 3.0], value=3.0,
                               help="특징값이 6개라 2σ면 정상 볼트도 4번 중 1번꼴로 '재측정'이 나옵니다. 3σ 권장.")
    st.write(f"수집된 정상 샘플: **{len(ss.samples)} / {target_n}**")
    dup = ss.result is not None and already_added(ss.result)
    if st.button("➕ 방금 측정값을 정상 샘플로 추가", width="stretch", disabled=ss.result is None or dup,
                 help="같은 측정은 한 번만 들어가요 (측정마다 고유 키로 구분)"):
        ok, msg_ = add_sample(ss.result, inspector)
        st.toast(msg_, icon=None if ok else "⚠️")
        st.rerun()
    if dup:
        st.caption("✔ 지금 화면의 측정은 이미 정상 샘플로 추가했어요.")
    st.progress(min(len(ss.samples) / target_n, 1.0))
    st.caption("정상 샘플은 추가할 때마다 `data/tap_samples.csv` 에 원본이 기록돼요 (샘플 초기화를 해도 파일은 그대로).")
    if len(ss.samples) < 3:
        st.caption("샘플이 3개 이상 모여야 아래 '정상 기준 계산 · 저장' 버튼이 눌립니다. "
                   "샘플을 추가해도 위 판정은 바뀌지 않고, 저장해야 새 기준이 적용됩니다.")
    if st.button("🎯 정상 기준 계산 · 저장", width="stretch", disabled=len(ss.samples) < 3):
        try:
            new = dict(f, schema_version=SCHEMA_VERSION, tap_ref=calc_tap_ref(ss.samples, k_sigma),
                       updated_at=now_kst_iso())
            store.save_flange(new)
            flanges.clear()
            ss.samples, ss.result = [], None   # sample_keys 는 남겨 두어 같은 측정이 다시 들어가지 않게 함
            st.toast(f"{fid} 정상 기준 저장 완료 (n={new['tap_ref']['n']}, ±{k_sigma}σ)")
            st.rerun()
        except ValueError as e:
            st.error(f"기준 저장 실패: {e}")
    if st.button("샘플 초기화", width="stretch"):
        ss.samples = []
        st.rerun()

# ---------------- 기준 ----------------
ref = f.get("tap_ref")
if ref:
    ref_src = f"실측 등록 n={ref['n']} ±{ref['k_sigma']}σ"
else:
    ref, ref_src = DEMO_REF, "데모 기준 (아직 등록 안 됨)"

# 저장된 기준에 진동이 없으면: 지금 모아 둔 정상 샘플(진동 값이 있는 것 3개 이상)로 진동 임시 기준을 계산해서 씀.
# 숫자를 고정해 두지 않고 샘플을 추가할 때마다 다시 계산됨. '정상 기준 계산 · 저장'을 누르면 저장된 기준이 우선.
prov_n, acc_default = 0, False
if ref.get("acc") is None:
    acc_samples = [x for x in ss.samples if x.get("acc")]
    if len(acc_samples) >= 3:
        try:
            ref = dict(ref, acc=calc_tap_ref(acc_samples, k_sigma)["acc"])
            prov_n = len(acc_samples)
            ref_src += f" + 진동 임시 기준(샘플 {prov_n}개, 저장 전)"
        except ValueError:
            pass
    if prov_n == 0:  # 샘플도 3개 미만 → 자리표시용 넓은 기본 범위 (샘플이 모이면 위 계산값으로 자동 교체)
        ref = dict(ref, acc=ACC_DEFAULT_REF)
        acc_default = True
        ref_src += " + 진동 임시 기본 기준(샘플 3개 이상 모이면 자동 교체)"

st.title("타음 검사")
c1, c2, c3, c4 = st.columns(4)
c1.metric("검사 대상", f"{fid}-{bolt}")
c2.metric("센서", "음향 + 진동", help="INMP441 마이크 + MPU6050 가속도계")
c3.metric("판정 기준", f"실측 n={ref['n']}" if f.get("tap_ref") else "데모 기준", help=ref_src)
c4.metric("이번 측정 횟수", f"{ss.count} 회")

# ---------------- 폰·태블릿 측정 자동 받기 ----------------
def phone_result(rec):
    """폰이 저장한 기록 1건 -> 이 화면의 결과 모양. key = 기록 ID (측정마다 고유)"""
    return {"features": rec["tapping"]["features"], "tapping": rec["tapping"], "doc": rec, "sim": False,
            "spectrum": rec["tapping"].get("spectrum"), "source": PHONE, "key": rec["record_id"]}


def phone_poll():
    """폰 앱이 Firebase 에 저장한 기록 중, 이 방식을 켠 시점(2분 전부터) 이후의 새 기록을 가져옴.
    '시각 범위'로 읽기 때문에 예전·미래 날짜의 시험 기록이 섞여 있어도 영향이 없음."""
    now = pd.Timestamp.now(tz="Asia/Seoul")
    if ss.get("phone_since") is None:
        ss.phone_since = (now - pd.Timedelta(minutes=2)).isoformat(timespec="seconds")
    try:
        recs = store.inspections_between(ss.phone_since, (now + pd.Timedelta(minutes=5)).isoformat(timespec="seconds"), 5)
    except Exception as e:
        st.error(f"폰 기록을 읽지 못했어요: {e}")
        return
    cand = [r for r in recs if r.get("type") == "BOLT" and r.get("device_id") not in PC_DEVICES
            and (r.get("tapping") or {}).get("model") == "range" and r["tapping"].get("features")]
    st.caption(f"📲 폰·태블릿 측정 대기 중 · {now:%H:%M:%S} 에 확인 · 이 시각 이후 폰 기록 {len(cand)}건 확인됨"
               + ("" if store.KEY.exists() else " · ⚠ key.json 이 없어 폰 기록을 받을 수 없어요"))
    ss.phone_recent = cand[:8]                      # 아래 '최근 폰 측정' 목록용 (새로 읽지 않고 이 값을 재사용)
    rec = cand[0] if cand else None
    if rec and rec["record_id"] != ss.phone_seen:
        ss.phone_seen = rec["record_id"]
        ss.result = phone_result(rec)
        ss.count += 1
        ss.last_saved = rec["record_id"]
        ss.pending_sel = (rec["flange_id"], rec["bolt_id"])
        st.cache_data.clear()                       # 새 기록이 이력 표에 바로 보이게
        st.rerun()                                  # 전체 화면을 다시 그려 아래 판정·게이지를 갱신


if source == PHONE:
    st.fragment(phone_poll, run_every=f"{phone_every}s")()
else:
    ss.phone_seen, ss.phone_since = None, None      # 다른 방식으로 바꿨다가 돌아오면 그 시점부터 다시 받음

# ---------------- 측정 ----------------
if source != PHONE and st.button("▶ 측정 시작", type="primary", width="stretch"):
    try:
        spec, mkey = None, None
        with st.spinner("신호 취득 → FFT → 특징값 추출 → 기준 비교 중... (ESP32 가 볼트를 한 번 타격해요)"):
            if source == "가상 데이터":
                time.sleep(.25)
                feats = mock_features(cond)
            else:
                feats, spec, mkey = read_serial(port, usb_cmd)
        tapping = tapping_from_features(feats, ref, ref_src, spec)
        if source == "ESP32 (USB)" and led_on and ss.get("ser"):   # 판정을 ESP32 LED 로 알림 (실패해도 측정은 계속)
            try:
                ss.ser.write(f"L,{tapping['result']}\n".encode())
            except Exception:
                pass
        at = now_kst_iso()
        doc = {"schema_version": SCHEMA_VERSION, "record_id": make_record_id(fid, bolt, at), "type": "BOLT",
               "flange_id": fid, "bolt_id": bolt, "inspector": inspector or "미입력", "device_id": "TAP-USB" if source == "ESP32 (USB)" else "PC-SIM",
               "inspected_at": at, "vision": None, "gap": None, "tapping": tapping,
               "final_result": tapping["result"], "app_version": APP_VERSION}
        ss.result = {"features": feats, "tapping": tapping, "doc": doc, "sim": source == "가상 데이터",
                     "spectrum": spec, "source": source, "key": mkey or doc["record_id"]}
        ss.count += 1
        if autosave:
            store.save_inspection(doc)
            ss.last_saved = doc["record_id"]
            st.cache_data.clear()
        st.rerun()  # 사이드바 버튼(샘플 추가)이 새 결과를 보도록 다시 그림
    except Exception as e:  # 포트 오류, 시간 초과, 스키마 오류 등
        st.error(f"측정 실패: {e}")

r = ss.result
if r is None:
    st.info("폰·태블릿에서 측정하면 여기에 나타나요." if source == PHONE
            else "왼쪽에서 플랜지·볼트를 고르고 '측정 시작'을 누르세요.")
    st.stop()

# 기준이 바뀌었으면 화면의 결과를 현재 기준으로 다시 판정 (조원 V3 와 같은 동작)
tp = tapping_from_features(r["features"], ref, ref_src, r.get("spectrum"))

# ---------------- 1. 큰 판정 ----------------
ui.banner(f"{r['doc']['flange_id']}-{r['doc']['bolt_id']} 종합 판정", tp["result"],
          f"범위를 벗어난 특징값 {tp['score']}개 · 기준: {ref_src}"
          + (f" · 저장됨 {ss.last_saved}" if ss.last_saved == r["doc"]["record_id"] else " · 저장 안 됨"))
if r["features"]["mic"]["mag"] >= 0.98:
    st.warning("소리가 너무 커서 잘렸습니다(Peak Magnitude ≈ 1). 마이크를 조금 떨어뜨리거나 더 약하게 치세요. "
               "이 측정은 정상 샘플로 추가할 수 없어요.")
if not autosave and ss.last_saved != r["doc"]["record_id"]:
    if st.button("💾 이 결과 저장"):
        store.save_inspection(r["doc"])
        ss.last_saved = r["doc"]["record_id"]
        st.cache_data.clear()
        st.rerun()

# ---------------- 2. 센서별 판정 + 근거 ----------------
SNAME = {"mic": "음향", "acc": "진동"}
FMT = {"peak_hz": (" Hz", ".0f"), "mag": ("", ".3f"), "energy_pct": (" %", ".1f")}
UNIT = {"mic": {"peak_hz": "Hz", "mag": "0~1", "energy_pct": "%"},     # 음향 크기 = 최대치를 1로 본 비율(단위 없음)
        "acc": {"peak_hz": "Hz", "mag": "g", "energy_pct": "%"}}      # 진동 크기 = g(중력가속도)


def fmt_of(sensor, k):
    """게이지·숫자에 붙일 (단위, 소수점 자리). 진동 크기만 ' g'"""
    return (" g", ".3f") if (sensor, k) == ("acc", "mag") else FMT[k]


def label(sensor, k):
    """예: Peak Frequency (Hz) / Peak Magnitude (g) / Peak Magnitude (0~1)"""
    return f"{FEATURE_KO[k]} ({UNIT[sensor][k]})"
for s in ("mic", "acc"):  # 값은 왔는데 기준이 없어 판정에서 빠진 센서 알림
    if r["features"].get(s) and not ref.get(s):
        st.warning(f"{SNAME[s]} 센서 값은 들어왔지만 정상 기준에 {SNAME[s]} 기준이 없어서 판정에서 빠졌어요. "
                   f"왼쪽에서 정상 볼트를 ESP32 로 측정해 '정상 샘플로 추가'를 3번 이상 하면 "
                   f"{SNAME[s]} 기준이 샘플대로 계산돼 바로 판정에 쓰이고, '정상 기준 계산 · 저장'을 누르면 저장됩니다.")
if acc_default and r["features"].get("acc"):
    st.caption("📳 진동 기준은 아직 임시 기본값(센서 전체 범위)이라 거의 항상 '정상'이 나와요. 정상 볼트를 측정해 "
               "'➕ 정상 샘플로 추가'를 3번 이상 하면 그 샘플로 기준이 바뀌어요.")
if prov_n:
    st.caption(f"📳 진동 기준은 지금 모은 정상 샘플 {prov_n}개로 계산한 임시 기준이에요 (샘플을 추가하면 바뀌고, 저장하면 확정).")
cols = st.columns(2)
for col, s in zip(cols, ("mic", "acc")):
    with col:
        name = "🎤 음향 · INMP441" if s == "mic" else "📳 진동 · MPU6050"
        feats, rr = r["features"].get(s), ref.get(s)
        if feats is None:
            st.info(f"{name} · 이번 측정에 {SNAME[s]} 값이 오지 않았어요"
                    " (ESP32 시리얼 모니터에서 '# MPU6050 OK' 가 나오는지, 메시지에 af 값이 있는지 확인)")
            continue
        if rr is None:
            st.info(f"{name} · 값은 들어왔지만 정상 기준이 없어 판정 제외")
            mc = st.columns(3)
            for c_, k in zip(mc, ("peak_hz", "mag", "energy_pct")):
                c_.metric(label(s, k), f"{feats[k]:{fmt_of(s, k)[1]}}{fmt_of(s, k)[0]}")
            continue
        res = tp["sensor_results"][s]
        ui.tile(name, res, [" &nbsp;|&nbsp; ".join(
            f"{label(s, k)} {'✓' if ok else '✕'}" for k, ok in tp["checks"][s].items())])
        for k in ("peak_hz", "mag", "energy_pct"):
            st.plotly_chart(ui.gauge(label(s, k), feats[k], rr[k][0], rr[k][1], *fmt_of(s, k)),
                            width="stretch", key=f"g_{s}_{k}")

with st.expander("판정 규칙"):
    st.code("센서 2개(음향 INMP441, 진동 MPU6050)마다 특징값 3개(Peak Frequency, Peak Magnitude, Band Energy)를\n"
            "정상 기준 범위와 비교해서, 범위를 벗어난 개수로 센서별 판정\n"
            f"  벗어난 개수 {RANGE_RULE['check'] - 1} 이하 → 정상 / {RANGE_RULE['check']}개 → 재측정 필요 / "
            f"{RANGE_RULE['ng']}개 이상 → 체결 이상 의심\n"
            "종합 판정 = 두 센서 중 더 나쁜 쪽 (한 센서만 이상해도 종합이 나빠짐)\n"
            f"정상 범위 = 정상 샘플 평균 ± k × 표준편차   (지금 이 플랜지: k = {ref.get('k_sigma', '데모')})", language=None)

# ---------------- 3. FFT (ESP32 가 보낸 실제 FFT 막대) ----------------
spec = tp.get("spectrum")
if spec:
    fcols = st.columns(2)
    for col, s_ in zip(fcols, ("mic", "acc")):
        tr = spec.get(s_)
        if not tr or not r["features"].get(s_):
            continue
        pk = r["features"][s_]["peak_hz"]
        band = ref[s_]["peak_hz"] if ref.get(s_) else None
        col.plotly_chart(ui.spectrum_bars(tr, pk, band, f"Peak {pk / 1000:.2f} kHz" if pk >= 1000 else f"Peak {pk:.0f} Hz"),
                         width="stretch", key=f"fft_{s_}")
        col.caption(f"{SNAME[s_]} FFT · 연한 칸 = 정상 Peak 주파수 범위, 세로선 = 이번 Peak")
elif r["sim"]:
    st.caption("가상 데이터에는 FFT 그래프가 없어요. 실제 ESP32·폰 측정에서만 나와요.")
else:
    st.caption("이 측정에는 FFT 데이터가 없어요 (예전 펌웨어/앱으로 측정한 기록).")

# ---------------- 4. 등록된 기준 + 이 볼트 이력 ----------------
with st.expander("현재 판정 기준 보기"):
    rows = []
    for s in ("mic", "acc"):
        for k in ("peak_hz", "mag", "energy_pct"):
            rr, ff = ref.get(s), r["features"].get(s)
            if rr is None:
                rows.append([SNAME[s], label(s, k), None, None, ff[k] if ff else None, "기준 없음"])
            else:
                v = ff[k] if ff else None
                rows.append([SNAME[s], label(s, k), rr[k][0], rr[k][1], v,
                             "-" if v is None else ("범위 안" if rr[k][0] <= v <= rr[k][1] else "범위 밖")])
    st.dataframe(pd.DataFrame(rows, columns=["센서", "특징값", "하한", "상한", "이번 측정값", "결과"]),
                 hide_index=True, width="stretch")

if source == PHONE and ss.phone_recent:
    st.subheader("최근 폰 측정 (정상 샘플로 추가)")
    st.caption("정상 볼트를 측정한 기록만 골라 추가하세요. 이미 추가한 측정은 눌리지 않아요.")
    for rec in ss.phone_recent:
        res_ = phone_result(rec)
        mic_ = rec["tapping"]["features"]["mic"]
        c_a, c_b, c_c = st.columns([3, 2, 2])
        c_a.write(f"{rec['inspected_at'][11:19]} · {rec['flange_id']}-{rec['bolt_id']} · 음향 {mic_['peak_hz']:.0f} Hz")
        c_b.write(ui.KO[rec["final_result"]])
        done = already_added(res_)
        if c_c.button("✔ 추가됨" if done else "➕ 샘플로 추가", key=f"addp_{rec['record_id']}", disabled=done):
            ok, msg_ = add_sample(res_, inspector)
            st.toast(msg_, icon=None if ok else "⚠️")
            st.rerun()

st.subheader(f"{fid}-{bolt} 검사 이력")
@st.cache_data(ttl=20)
def bolt_hist(flange_id, bolt_id):      # 이 볼트 기록만 읽음 (전체를 읽으면 Firebase 읽기 한도를 금방 씀)
    return store.inspections_for_bolt(flange_id, bolt_id)


hist = bolt_hist(fid, bolt)
if hist:
    h = pd.json_normalize(hist).sort_values("inspected_at", ascending=False)
    h["판정"] = h.final_result.map(ui.KO)
    show = {"inspected_at": "시간", "inspector": "검사자", "판정": "판정",
            "tapping.features.mic.peak_hz": "음향 Peak(Hz)", "tapping.features.acc.peak_hz": "진동 Peak(Hz)",
            "tapping.score": "이탈 수", "tapping.ref_source": "기준"}
    t = h[[c for c in show if c in h.columns]].rename(columns=show)
    t["시간"] = pd.to_datetime(t["시간"]).dt.strftime("%m/%d %H:%M:%S")
    st.dataframe(t.style.map(ui.badge_style, subset=["판정"]).format(
        {c: "{:.1f}" for c in ("음향 Peak(Hz)", "진동 Peak(Hz)") if c in t} | {"이탈 수": "{:.0f}"}, na_rep="-"),
        hide_index=True, width="stretch")
else:
    st.caption("아직 이 볼트의 저장된 기록이 없습니다.")
