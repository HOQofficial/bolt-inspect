# bolt-inspect — 작업 안내 (Claude Code 용)

## 사용자
- 한국어로만 대화. 초보자라 단계별로, 명령은 복사해서 붙이면 되게.
- Windows, 프로젝트 위치 `C:\Users\user\Desktop\bolt-inspect`, 가상환경 `.venv` (Python 3.14), PowerShell.
- 애매하면 한 번 물어보고 진행. 큰 작업은 스스로 검증 후 진행.

## 프로젝트 (2주 학생 프로젝트: 선박 기관부 플랜지 볼트 검사)
- 역할: 1 타음 장치 / 2 ESP32 판정 / 3 비전 / 4 저장·시각화 / 5 AI 영상
- 타음: 타격음 FFT 특징 3개(peak_hz, mag, energy_pct) × 센서(mic=INMP441, acc=MPU6050).
  range 판정: 정상 범위 밖 특징 0개=OK, 1개=CHECK, 2개 이상=NG. 기준 = 평균 ± 3σ.
- 비전: 볼트 돌출 = (너트 윗면 y − 볼트 끝 y) × (너트 높이 mm / 너트 높이 px). 나사산 수 = 돌출 ÷ 피치.
  플랜지 틈 = 4지점(12·3·6·9시) 측정.
- 결과 표기: OK/CHECK/NG → 정상 / 재측정 필요 / 체결 이상 의심.

## 구조
- `schema/` 스키마 v1.2 (flanges, inspections). 필드 이름 바꾸지 말 것.
  v1.2 변경: vision.marking(I-마킹: gap_pct, method, color, result) 추가, vision.protrusion_mm/thread_count 가 null 허용(마킹만 검사할 때).
- `tools/schema_rules.py` 공용 판정 규칙, 
  `tools/vision_measure.py` 비전 계산 + YOLO 검출(`detect` → pair_boxes, 너트만 찾으면 점 2개 반환),
  `tools/merge_public_data.py` 공개 데이터 zip 합치기 (class_map.txt, --need-both).
- `dashboard/` Streamlit: app.py(메뉴) · home.py · tapping.py · vision.py · store.py(key.json 있으면 Firestore, 없으면 local_db/) · ui.py
- `web/` 태블릿 PWA (Web Bluetooth), `esp32/tap_v1/` BLE 20바이트 청크 + `\n` 종료.
- 실행: `streamlit run dashboard/app.py`

## 현재 상태 (2026-10-05)
- 비전 AI: NPU-BOLT(Roboflow, CC BY 4.0) 사용. `data/public_zips/class_map.txt` 에 `bolt_b = nut`, 나머지 버림.
  합치기 완료: 학습 197장 / 검증 51장, nut 768개, bolt_tip 0개 (볼트 끝 라벨 없음).
- 앱 동작 방식: AI 가 너트를 찾아 ①② 자동, ③ 볼트 끝만 사람이 클릭.
- NPU-BOLT 로 학습한 bolt_yolo.pt 를 models/ 에 넣고 앱에서 동작 확인함 (너트 신뢰도 0.94~0.95).
- 다음 할 일: 실물 볼트 옆모습 사진 + 캘리퍼 실측으로 정확도 표 만들기, I-마킹 실사진 테스트.
- 비전 페이지 모드 3개: 볼트 돌출 / I-마킹(풀림 표시) / 플랜지 틈. I-마킹 판정: 끊김 ≤10% 정상, ≤20% 재측정, 초과 이상 (schema_rules.judge_marking).
- 이전 BNA 데이터(위에서 찍은 분리된 너트·볼트)는 폐기.

## 절대 하지 말 것
- `key.json` 커밋·공유 금지 (.gitignore 에 있음).
- 스키마 필드 이름 혼자 바꾸기 금지.
