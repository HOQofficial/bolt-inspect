볼트 FFT 대시보드 V3

추가 기능
- 정상 볼트 측정값을 기준 샘플로 누적
- 수집 샘플의 평균/표준편차를 이용해 정상 범위 자동 등록
- 기준 범위 폭(±1~3σ) 선택
- Peak Frequency / Peak Magnitude / Band Energy 항목명 명확화
- 센서별 판정 근거(✓/✕) 표시
- 종합 판정 로직 화면 표시
- 검사 이력 간소화 + 상세보기
- 등록된 정상 기준 표 표시

실행
python -m streamlit run app.py

현재 센서 데이터는 가상 데이터입니다.
실제 ESP32 연결 시 make_mock() 부분을 Serial 수신 데이터로 교체합니다.
