"""타음 검사 - 조원 V3 화면을 스키마 v1.1 에 맞게 옮긴 것.

측정 -> 특징값 6개 -> 기준 범위 비교 -> 큰 판정 표시 -> 저장(Firestore 또는 local_db)
정상 기준은 플랜지마다 등록되어 저장됩니다(flanges.tap_ref).
"""
import json
import time

import pandas as pd
import streamlit as st

import store
import ui
from schema_rules import (FEATURE_KO, SCHEMA_VERSION, calc_tap_ref, features_from_msg,
                          make_record_id, now_kst_iso, tapping_from_features)
from sim import CONDITIONS, DEMO_REF, mock_features, mock_spectra
import audio_features

APP_VERSION = "1.1"
ss = st.session_state
for k, v in {"result": None, "samples": [], "count": 0, "last_saved": None}.items():
    ss.setdefault(k, v)


@st.cache_data(ttl=15)
def flanges():
    return {f["flange_id"]: f for f in store.list_flanges()}


def read_serial(port, timeout=10):
    """ESP32 가 USB 로 보내는 특징값 메시지 v2 한 줄을 기다림.
    포트를 매번 열면 ESP32 가 재부팅되므로 한 번 연 포트를 계속 씀."""
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
    end = time.time() + timeout
    while time.time() < end:
        line = ss.ser.readline().decode("utf-8", "ignore").strip()
        if line.startswith("{"):
            try:
                msg = json.loads(line)
                if msg.get("v") == 2:
                    return features_from_msg(msg)
            except ValueError:
                pass
    raise TimeoutError(f"{timeout}초 안에 ESP32 특징값(v2 메시지)이 오지 않았습니다. ▶ 측정 시작을 누른 뒤 BOOT 버튼을 짧게 눌렀는지, 올바른 펌웨어(tap_sim_v2)를 올렸는지 확인하세요.")


def read_wifi(addr, timeout=10, auto_tap=False):
    """ESP32 가 자체 Wi-Fi(SoftAP)로 보내는 특징값을 읽음.
    PC 가 ESP32 Wi-Fi(TAP-01)에 접속한 상태에서 http://<addr>/latest 를 확인해,
    측정 순번(seq)이 바뀌면 = 새 타격으로 보고 그 값을 돌려줌."""
    import urllib.request
    base = "http://" + addr.strip().removeprefix("http://").rstrip("/")

    def get(path):
        try:
            with urllib.request.urlopen(base + path, timeout=3) as r:
                return json.loads(r.read().decode("utf-8"))
        except OSError as e:
            raise ValueError(f"ESP32({base})에 연결할 수 없어요. PC 의 Wi-Fi 가 ESP32 Wi-Fi(TAP-01)에 "
                             f"연결돼 있는지 확인하세요. ({e})")

    start = get("/latest")["msg"].get("seq", 0)
    if auto_tap:
        get("/tap")
    end = time.time() + timeout
    while time.time() < end:
        msg = get("/latest")["msg"]
        if msg.get("seq", 0) != start and msg.get("v") == 2:
            return features_from_msg(msg)
        time.sleep(0.3)
    raise TimeoutError(f"{timeout}초 안에 새 측정이 오지 않았어요. ▶ 측정 시작을 누른 뒤 BOOT 버튼을 짧게 누르거나, "
                       "'테스트용 가짜 타격 자동 요청'을 켜세요.")


FL = flanges()
if not FL:
    st.error("등록된 플랜지가 없습니다. python tools/seed_firestore.py 로 가짜 플랜지를 먼저 올리세요.")
    st.stop()

# ---------------- 사이드바: 검사 설정 + 정상 기준 등록 ----------------
with st.sidebar:
    st.header("검사 설정")
    fid = st.selectbox("플랜지", sorted(FL))
    f = FL[fid]
    bolt = st.selectbox("볼트 (12시부터 시계방향)", [f"B{i:02d}" for i in range(1, f["bolt_count"] + 1)])
    inspector = st.text_input("검사자", value=ss.get("inspector", "홍길동"), key="inspector")
    source = st.radio("측정 방식", ["가상 데이터", "PC 마이크", "ESP32 (USB)", "ESP32 (Wi-Fi)"], horizontal=True,
                      help="PC 마이크 = 이어폰·헤드셋 마이크로 실제 타격음 테스트 (음향 센서만)")
    if source == "가상 데이터":
        cond = st.selectbox("가상 측정 조건", CONDITIONS)
    elif source == "PC 마이크":
        try:
            if st.button("🔄 마이크 다시 찾기", help="이어폰을 앱을 켠 뒤에 꽂았거나 다시 꽂았을 때"):
                audio_features.refresh_devices()
                st.rerun()
            mics = audio_features.list_mics()
            if not mics:
                st.error("마이크가 하나도 안 잡힙니다. ① 이어폰이 끝까지 꽂혔는지 ② Windows 설정 > 소리 > 입력에 "
                         "마이크가 보이는지 확인한 뒤 '🔄 마이크 다시 찾기'를 누르세요.")
            mic_idx = st.selectbox("마이크", [i for i, _ in mics], format_func=dict(mics).get,
                                   help="이어폰/헤드셋 이름이나 '마이크'가 들어간 장치를 고르세요. Stereo Mix 는 마이크가 아닙니다.")
            if "마이크 아님" in dict(mics).get(mic_idx, ""):
                st.warning("Stereo Mix 는 PC 스피커 소리를 녹음하는 장치라 볼트 소리가 안 들어갑니다. 다른 마이크를 고르세요.")
        except Exception as e:
            st.error(f"마이크를 찾을 수 없습니다: {e}  (pip install sounddevice)")
            mic_idx = None
        st.caption("측정 시작 후 2초 안에 마이크 가까이(10~20cm)에서 볼트를 한 번 두드리세요. "
                   "처음엔 '정상 기준 등록'부터 하세요 (데모 기준은 가상 데이터용).")
    elif source == "ESP32 (Wi-Fi)":
        wifi_addr = st.text_input("ESP32 주소", "192.168.4.1", help="ESP32 SoftAP 기본 주소. 시리얼 모니터 첫 줄에도 나옴")
        wifi_auto = st.toggle("테스트용 가짜 타격 자동 요청", value=False,
                              help="센서 없이 연결만 시험할 때: 측정 시작을 누르면 ESP32 에 /tap 을 보내 가짜 타격 1번을 만듦. "
                                   "실제 센서로 측정할 때는 끄고, 측정 시작 후 볼트를 치세요.")
        st.caption("PC 의 Wi-Fi 를 'TAP-01'(비밀번호 bolt1234)에 연결한 상태여야 해요. 이 동안 인터넷은 끊겨요 "
                   "(저장은 내 PC local_db 에 됨). 브라우저로 http://192.168.4.1 을 열면 ESP32 화면도 볼 수 있어요.")
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
        st.caption("Arduino IDE 의 시리얼 모니터는 꼭 닫으세요 (포트를 한 프로그램만 쓸 수 있어요). "
                   "▶ 측정 시작을 누른 뒤 10초 안에 ESP32 의 BOOT 버튼을 짧게 누르세요.")
    autosave = st.toggle("측정하면 자동 저장", value=True)

    st.divider()
    st.subheader("정상 기준 등록")
    st.caption(f"{fid} 에 저장됩니다. 정상 체결 볼트를 여러 번 측정한 뒤 등록하세요.")
    target_n = st.number_input("기준 측정 목표 횟수", 3, 100, 10)
    k_sigma = st.select_slider("기준 범위 폭 (평균 ± k×표준편차)", [1.0, 1.5, 2.0, 2.5, 3.0], value=3.0,
                               help="특징값이 6개라 2σ면 정상 볼트도 4번 중 1번꼴로 '재측정'이 나옵니다. 3σ 권장.")
    st.write(f"수집된 정상 샘플: **{len(ss.samples)} / {target_n}**")
    if st.button("➕ 방금 측정값을 정상 샘플로 추가", width="stretch", disabled=ss.result is None):
        ss.samples.append(ss.result["features"])
        st.toast(f"정상 샘플 {len(ss.samples)}개째 추가됨. 다시 '측정 시작' → 추가를 반복하세요.")
        st.rerun()
    st.progress(min(len(ss.samples) / target_n, 1.0))
    if len(ss.samples) < 3:
        st.caption("샘플이 3개 이상 모여야 아래 '정상 기준 계산 · 저장' 버튼이 눌립니다. "
                   "샘플을 추가해도 위 판정은 바뀌지 않고, 저장해야 새 기준이 적용됩니다.")
    if st.button("🎯 정상 기준 계산 · 저장", width="stretch", disabled=len(ss.samples) < 3):
        try:
            new = dict(f, schema_version=SCHEMA_VERSION, tap_ref=calc_tap_ref(ss.samples, k_sigma),
                       updated_at=now_kst_iso())
            store.save_flange(new)
            flanges.clear()
            ss.samples, ss.result = [], None
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

st.title("타음 검사")
c1, c2, c3, c4 = st.columns(4)
c1.metric("검사 대상", f"{fid}-{bolt}")
c2.metric("센서", "음향 + 진동", help="INMP441 마이크 + MPU6050 가속도계")
c3.metric("판정 기준", f"실측 n={ref['n']}" if f.get("tap_ref") else "데모 기준", help=ref_src)
c4.metric("이번 측정 횟수", f"{ss.count} 회")

# ---------------- 측정 ----------------
if st.button("▶ 측정 시작", type="primary", width="stretch"):
    try:
        spec = None
        with st.spinner("🔴 녹음 중! 지금 볼트를 두드리세요 (2초)" if source == "PC 마이크"
                        else "신호 취득 → FFT → 특징값 추출 → 기준 비교 중... (ESP32 는 볼트를 타격하세요)"):
            if source == "가상 데이터":
                time.sleep(.25)
                feats = mock_features(cond)
            elif source == "PC 마이크":
                if mic_idx is None:
                    raise ValueError("선택된 마이크가 없습니다. 왼쪽에서 마이크를 먼저 고르세요.")
                x, fs = audio_features.record(2.0, 48000, mic_idx)
                mic, fr, mg = audio_features.extract(x, fs)
                if mic is None:
                    raise ValueError(f"타격음이 감지되지 않았습니다 (최대 음량 {abs(x).max():.3f}). "
                                     "마이크 가까이에서 더 세게 두드려 보세요.")
                feats, spec = {"mic": mic, "acc": None}, (fr, mg)
            elif source == "ESP32 (Wi-Fi)":
                feats = read_wifi(wifi_addr, auto_tap=wifi_auto)
            else:
                feats = read_serial(port)
        tapping = tapping_from_features(feats, ref, ref_src)
        at = now_kst_iso()
        doc = {"schema_version": SCHEMA_VERSION, "record_id": make_record_id(fid, bolt, at), "type": "BOLT",
               "flange_id": fid, "bolt_id": bolt, "inspector": inspector or "미입력", "device_id": {"PC 마이크": "PC-MIC", "ESP32 (USB)": "TAP-USB", "ESP32 (Wi-Fi)": "TAP-WIFI"}.get(source, "PC-SIM"),
               "inspected_at": at, "vision": None, "gap": None, "tapping": tapping,
               "final_result": tapping["result"], "app_version": APP_VERSION}
        ss.result = {"features": feats, "tapping": tapping, "doc": doc, "sim": source == "가상 데이터",
                     "spec": spec, "source": source}
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
    st.info("왼쪽에서 플랜지·볼트를 고르고 '측정 시작'을 누르세요.")
    st.stop()

# 기준이 바뀌었으면 화면의 결과를 현재 기준으로 다시 판정 (조원 V3 와 같은 동작)
tp = tapping_from_features(r["features"], ref, ref_src)

# ---------------- 1. 큰 판정 ----------------
ui.banner(f"{r['doc']['flange_id']}-{r['doc']['bolt_id']} 종합 판정", tp["result"],
          f"범위를 벗어난 특징값 {tp['score']}개 · 기준: {ref_src}"
          + (f" · 저장됨 {ss.last_saved}" if ss.last_saved == r["doc"]["record_id"] else " · 저장 안 됨"))
if r.get("source") == "PC 마이크":
    m = r["features"]["mic"]
    if m["mag"] >= 0.98:
        st.warning("소리가 너무 커서 잘렸습니다(Peak Magnitude ≈ 1). 마이크를 20~30cm 떨어뜨리거나 더 약하게 치세요. "
                   "이 측정은 정상 샘플로 추가하지 마세요.")
    if m["peak_hz"] < 400:
        st.warning(f"주파수가 {m['peak_hz']:.0f} Hz 로 매우 낮습니다. 금속 '팅' 소리가 아니라 책상이나 이어폰 줄이 "
                   "부딪힌 '쿵' 소리일 수 있어요. 마이크를 손에 들지 말고 내려놓은 뒤, 쇠붙이를 볼펜으로 톡 쳐 보세요.")
if not autosave and ss.last_saved != r["doc"]["record_id"]:
    if st.button("💾 이 결과 저장"):
        store.save_inspection(r["doc"])
        ss.last_saved = r["doc"]["record_id"]
        st.cache_data.clear()
        st.rerun()

# ---------------- 2. 센서별 판정 + 근거 ----------------
cols = st.columns(2)
for col, s in zip(cols, ("mic", "acc")):
    with col:
        res = tp["sensor_results"][s]
        if res is None:
            st.info(f"{ui.KO[None]} · {'음향' if s == 'mic' else '진동'} 센서 데이터 없음")
            continue
        name = ("🎤 음향 · " + ("PC 마이크" if r.get("source") == "PC 마이크" else "INMP441")) if s == "mic" else "📳 진동 · MPU6050"
        ui.tile(name, res, [" &nbsp;|&nbsp; ".join(
            f"{FEATURE_KO[k]} {'✓' if ok else '✕'}" for k, ok in tp["checks"][s].items())])
        feats, rr = r["features"][s], ref[s]
        fmt = {"peak_hz": (" Hz", ".0f"), "mag": ("", ".3f"), "energy_pct": (" %", ".1f")}
        for k in ("peak_hz", "mag", "energy_pct"):
            st.plotly_chart(ui.gauge(FEATURE_KO[k], feats[k], rr[k][0], rr[k][1], *fmt[k]),
                            width="stretch", key=f"g_{s}_{k}")

with st.expander("판정 규칙"):
    st.code("센서마다 특징값 3개(Peak Frequency, Peak Magnitude, Band Energy)를 기준 범위와 비교\n"
            "  0개 이탈 → 정상 / 1개 이탈 → 재측정 필요 / 2개 이상 이탈 → 체결 이상 의심\n"
            "종합 판정 = 두 센서 중 더 나쁜 쪽", language=None)

# ---------------- 3. FFT ----------------
if r.get("spec"):
    fr, mg = r["spec"]
    st.plotly_chart(ui.spectrum(fr, mg, r["features"]["mic"]["peak_hz"],
                                f"Peak {r['features']['mic']['peak_hz'] / 1000:.2f} kHz"), width="stretch")
    st.caption("실제로 녹음한 타격음의 FFT 입니다.")
elif r["sim"]:
    fm, ms, fa, ac = mock_spectra(r["features"])
    a, b = st.columns(2)
    a.plotly_chart(ui.spectrum(fm, ms, r["features"]["mic"]["peak_hz"],
                               f"Peak {r['features']['mic']['peak_hz'] / 1000:.2f} kHz"), width="stretch")
    b.plotly_chart(ui.spectrum(fa, ac, r["features"]["acc"]["peak_hz"],
                               f"Peak {r['features']['acc']['peak_hz']:.0f} Hz"), width="stretch")
    st.caption("FFT 그래프는 가상 데이터 화면용입니다. 실제 ESP32 는 특징값만 보냅니다.")

# ---------------- 4. 등록된 기준 + 이 볼트 이력 ----------------
with st.expander("현재 판정 기준 보기"):
    rows = [[("음향" if s == "mic" else "진동"), FEATURE_KO[k], ref[s][k][0], ref[s][k][1]]
            for s in ("mic", "acc") if ref.get(s) for k in ("peak_hz", "mag", "energy_pct")]
    st.dataframe(pd.DataFrame(rows, columns=["센서", "특징값", "하한", "상한"]), hide_index=True, width="stretch")

st.subheader(f"{fid}-{bolt} 검사 이력")
hist = [d for d in store.list_inspections() if d["flange_id"] == fid and d["bolt_id"] == bolt]
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
