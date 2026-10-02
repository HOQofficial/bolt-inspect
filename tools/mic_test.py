"""이어폰(PC) 마이크로 타격음 테스트.

실행:
  python tools/mic_test.py --list          # 마이크 목록 보기
  python tools/mic_test.py                 # 기본 마이크로 테스트
  python tools/mic_test.py --device 3      # 목록의 3번 마이크로 테스트
  python tools/mic_test.py --save FL001_B01_t100_s1   # 녹음을 data/raw/ 에 wav 로 저장(학습용)

Enter 를 누르면 2초 동안 녹음합니다. 그 사이에 볼트(또는 쇠붙이)를 한 번 두드리세요.
"""
import argparse
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audio_features import extract, record

ap = argparse.ArgumentParser()
ap.add_argument("--list", action="store_true")
ap.add_argument("--device", type=int, default=None)
ap.add_argument("--save", default=None, help="파일 이름 앞부분 (예: FL001_B01_t100_s1)")
args = ap.parse_args()

import sounddevice as sd  # noqa: E402

if args.list:
    print(sd.query_devices())
    print("\n'>' 표시가 기본 입력 장치입니다. 입력 채널(in)이 1 이상인 것이 마이크입니다.")
    sys.exit(0)

dev = sd.query_devices(args.device, "input")
print(f"사용할 마이크: {dev['name']}  (기본 샘플링 {dev['default_samplerate']:.0f} Hz)")
fs = 48000 if dev["default_samplerate"] >= 48000 else int(dev["default_samplerate"])
raw = Path(__file__).resolve().parent.parent / "data" / "raw"
n = 0
while True:
    if input("\nEnter = 녹음 시작 / q + Enter = 끝내기 > ").strip().lower() == "q":
        break
    print("녹음 중... 지금 두드리세요!")
    x, fs = record(2.0, fs, args.device)
    feats, _, _ = extract(x, fs)
    level = float(np.abs(x).max())
    if feats is None:
        print(f"  타격음이 감지되지 않았습니다 (최대 음량 {level:.3f}). 마이크 가까이에서 더 세게 쳐 보세요.")
        continue
    if level > 0.98:
        print("  주의: 소리가 너무 커서 잘렸습니다(클리핑). 마이크를 조금 멀리 두세요.")
    print(f"  Peak Frequency {feats['peak_hz']:>8.1f} Hz | Peak Magnitude {feats['mag']:.3f} | Band Energy {feats['energy_pct']:.1f} %")
    if args.save:
        n += 1
        raw.mkdir(parents=True, exist_ok=True)
        p = raw / f"{args.save}_{n:03d}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
        print(f"  저장: {p}")
