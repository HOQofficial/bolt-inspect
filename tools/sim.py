"""가상 타음 데이터 (조원 V3 의 make_mock 을 옮겨 온 것).
실제 ESP32 가 연결되기 전까지 화면·저장 흐름을 시험할 때 씁니다.
"""
import numpy as np

CONDITIONS = ["정상 체결", "재측정 필요", "체결 이상 의심"]

# 초기 데모 기준값: 실제 기준 등록 전 UI 확인용 (조원 V3 DEFAULT_REF 와 같음)
DEMO_REF = {
    "mic": {"peak_hz": [3000.0, 3400.0], "mag": [0.70, 0.90], "energy_pct": [60.0, 80.0]},
    "acc": {"peak_hz": [400.0, 440.0], "mag": [0.60, 0.82], "energy_pct": [62.0, 82.0]},
}


def mock_features(cond="정상 체결", rng=None):
    g = rng or np.random.default_rng()
    if cond == "정상 체결":
        mf, mm, me = g.normal(3200, 65), g.normal(.80, .025), g.normal(69, 2)
        af, am, ae = g.normal(420, 7), g.normal(.71, .025), g.normal(72, 2)
    elif cond == "체결 이상 의심":
        mf, mm, me = g.normal(3820, 90), g.normal(.53, .03), g.normal(43, 3)
        af, am, ae = g.normal(335, 12), g.normal(.47, .03), g.normal(47, 3)
    else:
        mf, mm, me = g.normal(3440, 35), g.normal(.72, .03), g.normal(57, 2)
        af, am, ae = g.normal(445, 6), g.normal(.62, .025), g.normal(60, 2)
    clip = lambda v: float(np.clip(v, 0, 100))
    return {"mic": {"peak_hz": round(float(mf), 1), "mag": round(float(max(mm, 0)), 3), "energy_pct": round(clip(me), 1)},
            "acc": {"peak_hz": round(float(af), 1), "mag": round(float(max(am, 0)), 3), "energy_pct": round(clip(ae), 1)}}
