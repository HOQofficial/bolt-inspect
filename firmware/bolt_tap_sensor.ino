/*
  볼트 타격음 진단 센서 — ESP32 + INMP441(I2S 마이크) + BLE
  ------------------------------------------------------
  동작 순서:
    1) I2S 마이크에서 계속 오디오를 읽으며 진폭이 임계값을 넘는 "타격"을 감지
    2) 타격 직후 SAMPLES개 샘플을 버퍼에 캡처
    3) FFT로 주파수 스펙트럼 계산 → 공진주파수(피크), 스펙트럼 중심 산출
    4) 규정 토크 기준으로 미리 정해둔 정상 주파수 범위와 비교해 등급 판정
       (정상 / 이완 의심 / 과체결 의심)
    5) 판정 결과를 JSON 문자열로 만들어 BLE Notify로 앱에 전송

  필요 라이브러리 (Arduino IDE 라이브러리 매니저에서 설치):
    - arduinoFFT (by Enrique Condes) — 반드시 "버전 1.6.2"로 설치하세요.
      (2.x부터 API가 완전히 바뀌어 이 코드의 FFT.Windowing/.Compute 등이 동작하지 않습니다.
       라이브러리 매니저에서 설치 시 버전 드롭다운을 직접 선택할 수 있습니다.)
    - ESP32 보드 패키지: 보드 매니저에서 "esp32 by Espressif" 버전 2.0.x 선택 권장
      (3.x부터 BLE 스택 기본값이 바뀌어 이 코드의 BLEDevice.h 클래식 API와
       충돌할 수 있습니다. 2.0.17 등 2.x 계열이 가장 안전합니다.)

  하드웨어 연결 (INMP441 I2S MEMS 마이크 모듈 기준):
    INMP441 VDD -> ESP32 3.3V
    INMP441 GND -> ESP32 GND
    INMP441 L/R -> ESP32 GND (왼쪽 채널 고정)
    INMP441 WS  -> ESP32 GPIO25
    INMP441 SCK -> ESP32 GPIO32
    INMP441 SD  -> ESP32 GPIO33

  주의: TRIGGER_THRESHOLD, NORMAL_FREQ_MIN/MAX 값은 예시입니다.
        실제 시편을 타격해 시리얼 모니터에 찍히는 값을 보고 반드시 보정하세요.
*/

#include <driver/i2s.h>
#include <arduinoFFT.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ---------- I2S 핀 설정 ----------
#define I2S_WS   25
#define I2S_SCK  32
#define I2S_SD   33
#define I2S_PORT I2S_NUM_0

// ---------- FFT 설정 ----------
#define SAMPLES       1024      // FFT 포인트 수 (2의 거듭제곱)
#define SAMPLE_RATE   16000     // 샘플링 주파수 (Hz) — 최대 8kHz까지 분석 가능(나이퀴스트)

double vReal[SAMPLES];
double vImag[SAMPLES];
arduinoFFT FFT = arduinoFFT();

// ---------- BLE UUID (Nordic UART 서비스 형식을 그대로 재사용) ----------
#define SERVICE_UUID       "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHAR_MEASURE_UUID  "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  // Notify: 측정 결과
#define CHAR_CONFIG_UUID   "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  // Write: 임계값 설정

BLECharacteristic *pMeasureChar;
bool deviceConnected = false;

// ---------- 판정 기준값 (기획서 7.1 기준값 설계와 동일한 역할) ----------
// 정상 체결 시편을 여러 번 타격해 얻은 공진주파수 범위로 교체하세요.
float NORMAL_FREQ_MIN = 1100.0;   // Hz
float NORMAL_FREQ_MAX = 1400.0;   // Hz

// 타격 감지 임계값 — 조용한 상태의 진폭보다 충분히 크게 설정
const int32_t TRIGGER_THRESHOLD = 60000; // 시리얼 모니터로 보정

// ---------- (선택) 학습된 선형 SVM 계수 ----------
// tools/serial_logger.py 로 라벨링된 데이터를 모으고 tools/train_svm.py 로 학습하면
// 아래 형식의 계수가 출력됩니다. 그대로 붙여넣고 USE_SVM 을 1로 바꾸면
// 규칙 기반 대신 데이터 기반 판정(기획서 6.3의 SVM 방식)을 사용합니다.
#define USE_SVM 0
#if USE_SVM
// {w_peak_freq, w_centroid, w_decay} — 클래스별 가중치 (정상/이완/과체결 순)
const float SVM_W[3][3] = {
  {0, 0, 0},
  {0, 0, 0},
  {0, 0, 0}
};
const float SVM_B[3] = {0, 0, 0};
const char *SVM_CLASS_NAMES[3] = {"정상 체결", "이완 의심", "과체결 의심"};
#endif

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *s) override { deviceConnected = true; }
  void onDisconnect(BLEServer *s) override {
    deviceConnected = false;
    BLEDevice::startAdvertising(); // 연결 끊기면 다시 광고 시작
  }
};

// 앱에서 "MIN:1100" 또는 "MAX:1400" 형식으로 써서 임계값을 실시간 조정할 수 있게 함
class ConfigCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String v = String(c->getValue().c_str());
    if (v.startsWith("MIN:")) NORMAL_FREQ_MIN = v.substring(4).toFloat();
    else if (v.startsWith("MAX:")) NORMAL_FREQ_MAX = v.substring(4).toFloat();
  }
};

void setupI2S() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_PORT, &pins);
}

// 진폭이 임계값을 넘는 "타격" 순간까지 대기
bool waitForTap() {
  int32_t sample;
  size_t bytesRead;
  for (int i = 0; i < SAMPLE_RATE; i++) { // 최대 1초간 대기 후 리턴(워치독/BLE 처리 기회 제공)
    i2s_read(I2S_PORT, &sample, sizeof(sample), &bytesRead, portMAX_DELAY);
    int32_t scaled = sample >> 14; // 32비트 I2S 워드를 다루기 쉬운 범위로 축소
    if (abs(scaled) > TRIGGER_THRESHOLD) return true;
  }
  return false;
}

void captureBuffer() {
  int32_t raw[SAMPLES];
  size_t bytesRead;
  i2s_read(I2S_PORT, raw, sizeof(raw), &bytesRead, portMAX_DELAY);
  for (int i = 0; i < SAMPLES; i++) {
    vReal[i] = (double)(raw[i] >> 14);
    vImag[i] = 0.0;
  }
}

void setup() {
  Serial.begin(115200);
  setupI2S();

  BLEDevice::init("BoltTapSensor");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());
  BLEService *pService = pServer->createService(SERVICE_UUID);

  pMeasureChar = pService->createCharacteristic(
      CHAR_MEASURE_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  pMeasureChar->addDescriptor(new BLE2902());

  BLECharacteristic *pConfigChar = pService->createCharacteristic(
      CHAR_CONFIG_UUID, BLECharacteristic::PROPERTY_WRITE);
  pConfigChar->setCallbacks(new ConfigCallbacks());

  pService->start();
  BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
  BLEDevice::startAdvertising();

  Serial.println("BLE 광고 시작 — 앱에서 'BoltTapSensor' 검색 후 연결하세요.");
}

// 감쇠율(decay): 캡처 구간 앞쪽 절반 대비 뒤쪽 절반의 진폭(RMS) 비율.
// 값이 클수록 타격 직후 진폭이 빠르게 줄어드는(더 감쇠하는) 신호라는 뜻.
// 반드시 FFT.Windowing/.Compute 를 부르기 "전"의 시간영역 vReal에서 계산해야 함
// (그 함수들이 vReal/vImag를 주파수영역 값으로 덮어씀).
double computeDecay() {
  double sumFirst = 0, sumSecond = 0;
  for (int i = 0; i < SAMPLES / 2; i++) sumFirst += vReal[i] * vReal[i];
  for (int i = SAMPLES / 2; i < SAMPLES; i++) sumSecond += vReal[i] * vReal[i];
  double rmsFirst = sqrt(sumFirst / (SAMPLES / 2));
  double rmsSecond = sqrt(sumSecond / (SAMPLES / 2));
  return rmsSecond > 1.0 ? rmsFirst / rmsSecond : 0.0;
}

void classify(double peakFreq, double centroid, double decay, String &status, int &confidence) {
#if USE_SVM
  double scores[3];
  for (int c = 0; c < 3; c++) {
    scores[c] = SVM_W[c][0] * peakFreq + SVM_W[c][1] * centroid + SVM_W[c][2] * decay + SVM_B[c];
  }
  int best = 0;
  for (int c = 1; c < 3; c++) if (scores[c] > scores[best]) best = c;
  status = SVM_CLASS_NAMES[best];
  double sumExp = 0;
  for (int c = 0; c < 3; c++) sumExp += exp(scores[c] - scores[best]);
  confidence = (int)(100.0 / sumExp); // 소프트맥스 근사 신뢰도
#else
  if (peakFreq < NORMAL_FREQ_MIN) {
    status = "이완 의심";
    confidence = 78;
  } else if (peakFreq > NORMAL_FREQ_MAX) {
    status = "과체결 의심";
    confidence = 75;
  } else {
    status = "정상 체결";
    confidence = 92;
  }
#endif
}

void loop() {
  if (!waitForTap()) return;

  captureBuffer();
  double decay = computeDecay(); // FFT로 vReal이 덮어써지기 전에 먼저 계산

  FFT.Windowing(vReal, SAMPLES, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
  FFT.Compute(vReal, vImag, SAMPLES, FFT_FORWARD);
  FFT.ComplexToMagnitude(vReal, vImag, SAMPLES);

  double peakFreq = FFT.MajorPeak(vReal, SAMPLES, SAMPLE_RATE);

  // 스펙트럼 중심(spectral centroid) 계산
  double centroidNum = 0, centroidDen = 0;
  for (int i = 1; i < SAMPLES / 2; i++) {
    double f = (i * 1.0 * SAMPLE_RATE) / SAMPLES;
    centroidNum += f * vReal[i];
    centroidDen += vReal[i];
  }
  double centroid = centroidDen > 0 ? centroidNum / centroidDen : 0;

  String status;
  int confidence;
  classify(peakFreq, centroid, decay, status, confidence);

  String json = "{";
  json += "\"status\":\"" + status + "\",";
  json += "\"peak_freq\":" + String(peakFreq, 1) + ",";
  json += "\"centroid\":" + String(centroid, 1) + ",";
  json += "\"decay\":" + String(decay, 3) + ",";
  json += "\"confidence\":" + String(confidence);
  json += "}";

  Serial.println(json); // 캘리브레이션 시 여기 값을 보고 임계값을 조정

  // tools/serial_logger.py가 파싱하는 학습용 CSV 라인 (라벨은 로거가 붙임)
  Serial.print("DATA,");
  Serial.print(peakFreq, 2); Serial.print(",");
  Serial.print(centroid, 2); Serial.print(",");
  Serial.println(decay, 4);

  if (deviceConnected) {
    pMeasureChar->setValue(json.c_str());
    pMeasureChar->notify();
  }

  delay(500); // 같은 타격이 중복 감지되지 않도록 디바운스
}
