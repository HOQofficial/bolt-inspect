"""
serial_logger.py로 모은 data.csv를 가지고 선형 SVM을 학습하고,
ESP32 펌웨어(bolt_tap_sensor.ino)의 USE_SVM 블록에 그대로 붙여넣을 수 있는
C 배열 형태의 계수를 출력합니다. 기획서 6.3(학습과 추론)의 SVM 경로에 해당합니다.

설치:
    pip install numpy scikit-learn

사용법:
    python train_svm.py data.csv

data.csv 형식 (serial_logger.py가 자동 생성):
    peak_freq,centroid,decay,label
    1243.20,891.00,0.4200,normal
    980.10,760.30,0.5500,loose
    ...
label 값은 normal / loose / over 세 가지를 사용해야 합니다.
"""
import csv
import sys

import numpy as np
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.svm import LinearSVC

LABEL_ORDER = ["normal", "loose", "over"]
LABEL_KOREAN = {"normal": "정상 체결", "loose": "이완 의심", "over": "과체결 의심"}


def load_data(path):
    X, y = [], []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            X.append([float(row["peak_freq"]), float(row["centroid"]), float(row["decay"])])
            y.append(row["label"].strip())
    return np.array(X), np.array(y)


def main():
    if len(sys.argv) < 2:
        print("사용법: python train_svm.py data.csv")
        sys.exit(1)

    X, y = load_data(sys.argv[1])
    counts = {l: int((y == l).sum()) for l in LABEL_ORDER}
    print(f"샘플 수: {len(y)}  (클래스별: {counts})")

    missing = [l for l in LABEL_ORDER if counts.get(l, 0) == 0]
    if missing:
        print(f"오류: 다음 라벨의 데이터가 없습니다 — {missing}. "
              f"세 조건 모두 serial_logger.py로 수집한 뒤 다시 실행하세요.")
        sys.exit(1)

    if len(y) < 90:
        print("경고: 기획서 6.2 목표(조건별 20회 이상, 전체 100개 이상)에 못 미칩니다. "
              "아래 결과는 참고용으로만 쓰고, 더 모은 뒤 다시 학습하는 것을 권장합니다.")

    n_splits = max(2, min(5, min(counts.values())))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    clf = LinearSVC(multi_class="ovr", max_iter=20000)
    y_pred = cross_val_predict(clf, X, y, cv=skf)

    print("\n=== 교차검증 성능 (기획서 9.1 평가지표) ===")
    print(f"정확도(Accuracy): {accuracy_score(y, y_pred):.3f}  (PoC 목표: 0.70 이상)")
    print(classification_report(
        y, y_pred, labels=LABEL_ORDER,
        target_names=[LABEL_KOREAN[l] for l in LABEL_ORDER], zero_division=0))
    print("※ '이완 의심' 재현율(recall)이 기획서 목표(0.75 이상)를 만족하는지 확인하세요.")

    # 임베딩용 최종 모델은 전체 데이터로 다시 학습
    clf.fit(X, y)

    print("\n=== bolt_tap_sensor.ino 의 USE_SVM 블록에 붙여넣을 계수 ===\n")
    print("const float SVM_W[3][3] = {")
    for label in LABEL_ORDER:
        idx = list(clf.classes_).index(label)
        w = clf.coef_[idx]
        print(f"  {{{w[0]:.6f}f, {w[1]:.6f}f, {w[2]:.6f}f}}, // {LABEL_KOREAN[label]}")
    print("};")

    b_values = ", ".join(
        f"{clf.intercept_[list(clf.classes_).index(l)]:.6f}f" for l in LABEL_ORDER)
    print(f"const float SVM_B[3] = {{{b_values}}};")
    names = ", ".join(f'"{LABEL_KOREAN[l]}"' for l in LABEL_ORDER)
    print(f"const char* SVM_CLASS_NAMES[3] = {{{names}}};")
    print("\n붙여넣은 뒤 #define USE_SVM 1 로 바꾸고 재업로드하세요.")


if __name__ == "__main__":
    main()
