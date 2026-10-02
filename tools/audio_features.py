"""타격음 -> 특징값 3개 (스키마 v1.1 의 features.mic 와 같은 형식).

PC 마이크(이어폰 마이크) 테스트와 나중에 wav 파일 분석에 같이 씁니다.
ESP32 펌웨어도 아래 '정의'와 똑같이 계산해야 PC 결과와 비교할 수 있습니다.

정의
- peak_hz    : 200 Hz ~ 10 kHz 사이에서 가장 큰 주파수 성분
- mag        : 타격음의 최대 진폭 (0~1, 마이크 최대 입력 = 1). 세게 치면 커짐
- energy_pct : 200 Hz ~ 10 kHz 전체 에너지 중 2 ~ 10 kHz(고주파) 대역이 차지하는 비율(%)
"""
import numpy as np

LOW, HIGH = 200.0, 10000.0          # 분석 범위 (전원 잡음·손 떨림 제외)
BAND = (2000.0, 10000.0)            # Band Energy = 고주파 대역 비율 (풀리면 낮아지는 경향)
WINDOW_S = 0.10                     # 타격 후 분석 길이 100 ms


def find_hit(x, fs):
    """타격 시작 위치(샘플 번호). 소리가 너무 작으면 None."""
    a = np.abs(x)
    peak = a.max()
    noise = np.median(a) + 1e-9
    if peak < 0.02 or peak < noise * 8:
        return None
    return max(0, int(np.argmax(a > peak * 0.3)) - int(0.005 * fs))   # 시작 5 ms 전부터


def extract(x, fs):
    """x: 1채널 float 배열(-1~1). 반환 (features_mic, freqs, mags) 또는 타격 없으면 (None, None, None)"""
    x = np.nan_to_num(np.asarray(x, dtype=float).ravel(), nan=0.0, posinf=0.0, neginf=0.0)
    x = x - x.mean()
    i = find_hit(x, fs)
    if i is None:
        return None, None, None
    seg = x[i:i + int(WINDOW_S * fs)]
    n = 8192 if len(seg) <= 8192 else 1 << int(np.ceil(np.log2(len(seg))))
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    freqs = np.fft.rfftfreq(n, 1 / fs)
    hi = min(HIGH, fs / 2 * 0.95)
    use = (freqs >= LOW) & (freqs <= hi)
    power = spec ** 2
    band = use & (freqs >= BAND[0]) & (freqs <= BAND[1])
    feats = {
        "peak_hz": round(float(freqs[use][np.argmax(spec[use])]), 1),
        "mag": round(float(np.clip(np.abs(seg).max(), 0, 1)), 3),
        "energy_pct": round(float(100 * power[band].sum() / (power[use].sum() + 1e-12)), 1),
    }
    if not all(np.isfinite(v) for v in feats.values()):
        return None, None, None
    show = freqs <= hi
    return feats, freqs[show], spec[show] / (spec[use].max() + 1e-12)


def record(seconds=2.0, fs=44100, device=None):
    """PC 마이크로 녹음. sounddevice 필요 (pip install sounddevice)"""
    import sounddevice as sd
    x = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="float32", device=device)
    sd.wait()
    return x[:, 0], fs


def refresh_devices():
    """이어폰을 앱 실행 후에 꽂거나 뺐을 때 장치 목록을 새로 읽음 (PortAudio 재시작)."""
    import sounddevice as sd
    sd._terminate()
    sd._initialize()


def list_mics():
    """Windows 는 같은 장치가 여러 번(MME/DirectSound/WASAPI...) 나오므로 MME 기준으로 정리하고,
    진짜 마이크를 앞에, 'Stereo Mix'(스피커 소리를 녹음하는 가상 장치)는 뒤로 보냄.
    반환: [(장치번호, 표시이름), ...]"""
    import sounddevice as sd
    apis = sd.query_hostapis()
    devs = [(i, d) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] >= 1]
    mme = [(i, d) for i, d in devs if "MME" in apis[d["hostapi"]]["name"]]
    out = []
    for i, d in (mme or devs):          # MME 목록이 비면 전체 입력 장치 사용
        name = d["name"]
        low = name.lower()
        fake = any(k in low for k in ("stereo mix", "스테레오 믹스", "what u hear", "loopback"))
        mapper = "mapper" in low or "매퍼" in name
        rank = 2 if fake else (1 if mapper else 0)
        out.append((rank, i, name + ("  (스피커 소리 녹음용, 마이크 아님)" if fake else "")))
    return [(i, n) for _, i, n in sorted(out)]
