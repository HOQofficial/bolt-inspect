"""
ESP32가 시리얼로 출력하는 'DATA,peak_freq,centroid,decay' 라인을 읽어
라벨을 붙여서 CSV로 저장하는 도구.

기획서 6.2(데이터 확보와 라벨링) 절차를 그대로 따릅니다:
조건(정상/저체결/과체결)을 하나 고정하고 토크렌치로 해당 토크를 맞춘 뒤,
이 스크립트를 그 라벨로 실행한 상태에서 시편을 15~20회 이상 반복 타격하세요.
조건을 바꿀 때마다(다른 토크로 재체결) --label 값을 바꿔 다시 실행하면 됩니다.

설치:
    pip install pyserial

사용법:
    python serial_logger.py --port COM5 --label normal --out data.csv
    python serial_logger.py --port COM5 --label loose  --out data.csv
    python serial_logger.py --port COM5 --label over   --out data.csv

label 값: normal(정상 토크 100%) / loose(저체결 50%) / over(과체결 150%)
Ctrl+C로 종료합니다. 같은 --out 파일에 계속 이어서 쌓입니다.
"""
import argparse
import csv
import os

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, help="예: COM5, /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--label", required=True, choices=["normal", "loose", "over"])
    parser.add_argument("--out", default="data.csv")
    args = parser.parse_args()

    file_exists = os.path.exists(args.out)
    ser = serial.Serial(args.port, args.baud, timeout=1)

    with open(args.out, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["peak_freq", "centroid", "decay", "label"])

        print(f"'{args.label}' 라벨로 기록 시작. 시편을 반복 타격하세요. (Ctrl+C 종료)")
        count = 0
        try:
            while True:
                line = ser.readline().decode(errors="ignore").strip()
                if not line.startswith("DATA,"):
                    continue
                parts = line.split(",")
                if len(parts) != 4:
                    continue
                _, peak_freq, centroid, decay = parts
                writer.writerow([peak_freq, centroid, decay, args.label])
                f.flush()
                count += 1
                print(f"[{count}] freq={peak_freq} centroid={centroid} decay={decay}")
        except KeyboardInterrupt:
            print(f"\n종료. 총 {count}개 샘플을 {args.out}에 저장했습니다.")


if __name__ == "__main__":
    main()
