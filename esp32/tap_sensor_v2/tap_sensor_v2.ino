// tap_sensor_v2.ino - 실제 센서(INMP441 마이크 + MPU6050 진동)로 타격음을 재고, 특징값 + FFT 막대를 블루투스로 보내는 펌웨어
// 보드: ESP32-DevKitC V4 (ESP32-WROOM-32E)  /  Arduino 보드 선택: ESP32 Dev Module
// 꼭 설정: 도구(Tools) → Partition Scheme → "Huge APP (3MB No OTA/1MB SPIFFS)"  (블루투스를 켜므로 필요)
// 추가 라이브러리 설치 필요 없음 (FFT 도 이 파일 안에 있음)
//
// ---------------- 배선 ----------------
//  INMP441  VDD→3.3V  GND→GND  L/R→GPIO27(코드가 LOW 로 고정)  WS→GPIO25  SCK→GPIO32  SD→GPIO33
//  MPU6050  VCC→3.3V  GND→GND  SDA→GPIO21  SCL→GPIO22  (AD0, INT 는 연결 안 함)
//  솔레노이드 MOSFET 모듈  제어(SIG/게이트)→GPIO23, GND 는 ESP32 GND 와 공통, 솔레노이드 전원(12V)은 따로
//        (솔레노이드에 역기전력 방지 다이오드, 게이트에 10 kΩ 풀다운 권장)
//  판정 LED  초록 GPIO13 / 빨강 GPIO14 (+ 가짜 GND 16, 17). 자세한 건 LED_배선_가이드.md
//
// ---------------- 동작 (이번 버전부터 '명령할 때만' 측정) ----------------
//  예전: 소리가 나면 무조건 측정 → 주변 소리에도 계속 측정되어 Firebase 한도를 다 씀
//  지금: 아래 신호가 있을 때만 '딱 1번' 측정하고 끝. 신호가 없으면 마이크에 큰 소리가 나도 무시.
//    S  = 솔레노이드로 타격 + 측정 1회   (폰 앱 '타격' 버튼 / 시리얼 'S' / BOOT 버튼 짧게)
//    M  = 손으로 칠 때 측정 대기 8초       (폰 앱 '손으로 칠게요' 버튼 / 시리얼 'M' / BOOT 버튼 1초 꾹)
//    BOOT 대신 쓸 스위치: GPIO0 과 GND 사이에 푸시 스위치를 달면 BOOT 버튼과 똑같이 동작
//  측정 순서: 타격 소리 100 ms 녹음 → FFT → 특징값 3개 (음향)
//             같은 순간의 진동(MPU6050, 1 kHz) 256 ms → FFT → 특징값 3개 (진동)
//  결과 한 줄(메시지 v2)을 블루투스(와 USB 시리얼)로 보냄:
//      {"v":2,"seq":순번,"k":"부팅번호-순번","src":"mic","mf":..,"mm":..,"me":..,"af":..,"am":..,"ae":..,"sm":[50개],"sa":[32개]}
//      k = 측정마다 다른 고유 번호 (같은 측정을 정상 샘플로 두 번 넣지 않게 구분하는 키)
//      sm/sa = FFT 그래프용 막대 (0~99). sm: 0~8000 Hz 를 50칸, sa: 0~500 Hz 를 32칸
//  소리를 못 들으면 {"v":2,"evt":"miss"} 한 줄을 보냄 (앱에 '소리를 못 들었어요' 표시)
//  - 시리얼 모니터 글자: S = 타격, M = 측정 대기, d = 센서 값 계속 보기(배선 확인용), L,OK / L,CHECK / L,NG / L,OFF = 판정 LED
//  - 판정 LED: 초록(정상) / 빨강 깜빡임(재측정) / 빨강(체결 이상 의심). 폰(블루투스 쓰기)·PC(USB "L,OK")가 판정 결과를 보내 줌
//  - BLE: 이름 TAP-01 (web/app 과 같은 UUID, 20바이트씩 나눠 보내고 줄바꿈으로 끝)

#define AUTO_DETECT 0       // 0 = 명령(S/M/BOOT)이 있을 때만 측정 (기본).  1 = 예전처럼 소리가 나면 무조건 측정 (시험용)

#include <Wire.h>
#include "driver/i2s.h"
#include "driver/gpio.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>

// ---------------- 설정 ----------------
const char* NAME = "TAP-01";            // BLE 이름 (장치마다 TAP-01, TAP-02 ...)
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHAR_UUID    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   // 측정값 보내는 통로 (ESP32 → 폰, notify)
#define RX_UUID      "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   // 폰이 보내는 명령 통로 (폰 → ESP32, write) : LED, 타격
#define PIN_WS 25
#define PIN_SCK 32
#define PIN_SD 33
#define PIN_SDA 21
#define PIN_SCL 22
#define BOOT_PIN 0
const int FAKE_GND_MIC_LR = 27;         // 마이크 L/R 핀을 연결한 곳. 아래 setup() 에서 LOW 로 고정해 GND 처럼 씀
const int MOSFET_GATE = 23;             // 솔레노이드 MOSFET 제어 핀. 평소 LOW(꺼짐), 타격할 때만 잠깐 HIGH
// ---- 솔레노이드 타격 ----
const unsigned long STRIKE_MS = 40;         // 솔레노이드를 켜 두는 시간(ms). 기준은 이 세기로 만든 것이므로 정한 뒤 바꾸지 마세요
const unsigned long STRIKE_MIN_GAP_MS = 500;// 타격 사이 최소 간격 (솔레노이드 과열 방지)
const unsigned long STRIKE_WAIT_MS = 600;   // 타격한 뒤 소리를 기다려 주는 시간
const unsigned long HAND_WAIT_MS = 8000;    // 손으로 칠 때 소리를 기다려 주는 시간
// ---- 판정 LED (조원 작성 코드 반영) ----
// LED 의 (+)쪽: 저항(220~330Ω)을 거쳐 아래 핀에 연결. LED 의 (-)쪽: 아래 '가짜 GND' 핀에 연결 (이 핀을 LOW 로 고정해서 GND 처럼 씀)
#define PIN_LED_GREEN 13
#define PIN_LED_RED   14
#define PIN_GND_GREEN 16
#define PIN_GND_RED   17
const unsigned long LED_HOLD_MS = 15000;   // 판정 불빛을 켜 두는 시간 (0 이면 다음 판정·OFF 명령까지 계속)
const unsigned long LED_BLINK_MS = 400;    // 재측정(CHECK) 은 빨강이 이 간격으로 깜빡임
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

const int   FS = 32000;                 // 마이크 샘플링 32 kHz (10 kHz 까지 분석)
const int   BLK = 256;                  // 한 번에 읽는 샘플 수 (8 ms)
const int   CAP_N = BLK * 13;           // 녹음 버퍼 (직전 8 ms + 타격 후 약 96 ms)
const int   SEG_N = 3200;               // 분석 길이 100 ms
const int   NFFT = 4096;
const float TRIG_MIN = 0.02;            // 타격으로 볼 최소 크기 (0~1). 주변이 시끄러우면 자동으로 올라감
const float TRIG_X_NOISE = 6.0;         // 소음의 몇 배를 넘으면 타격으로 볼지
const unsigned long COOLDOWN_MS = 600;  // 한 번 측정한 뒤 다시 측정하기까지 쉬는 시간
const int   ACC_FS = 1000, ACC_N = 1024, ACC_SEG = 256;
// FFT 그래프용 막대 (앱 화면에 그림). 값을 바꾸면 web/app 의 SP_* 상수도 같이 바꿔야 함
const int   SP_MIC_N = 50;  const float SP_MIC_FMAX = 8000;
const int   SP_ACC_N = 32;  const float SP_ACC_FMAX = 500;

// ---------------- 상태 ----------------
float *cap, *re, *im, *accBuf;          // 큰 버퍼는 블루투스를 켠 뒤에 메모리를 받음 (setup 참고)
volatile uint32_t accIdx = 0;
float accLast = 0;
bool mpuOk = false, micOk = false, debugOn = false;
uint32_t micNonZero = 0;
float noise = 0.005;
unsigned long lastTrig = 0, seq = 0;
uint32_t bootId = 0;                    // 켤 때마다 달라지는 번호 (측정 고유 키 만들 때 씀)
char lastMsg[620] = "{\"v\":2,\"seq\":0}";
int32_t raw[BLK * 2];
float prevBlk[BLK], curBlk[BLK];
uint8_t spMic[SP_MIC_N], spAcc[SP_ACC_N];
// 명령 상태: 측정은 armed 일 때만 함
volatile bool reqStrike = false, reqHand = false;   // 블루투스 콜백이 세워 두면 loop 가 처리
bool armed = false;
unsigned long armUntil = 0;
bool gateOn = false;
unsigned long gateOffAt = 0, lastStrike = 0;

// ---------------- FFT (반복 radix-2) ----------------
void fft(float* xr, float* xi, int n) {
  for (int i = 1, j = 0; i < n; i++) {
    int bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { float t = xr[i]; xr[i] = xr[j]; xr[j] = t; t = xi[i]; xi[i] = xi[j]; xi[j] = t; }
  }
  for (int len = 2; len <= n; len <<= 1) {
    float ang = -2 * PI / len, wr = cos(ang), wi = sin(ang);
    for (int i = 0; i < n; i += len) {
      float cr = 1, ci = 0;
      for (int k = 0; k < len / 2; k++) {
        int a = i + k, b = a + len / 2;
        float tr = xr[b] * cr - xi[b] * ci, ti = xr[b] * ci + xi[b] * cr;
        xr[b] = xr[a] - tr; xi[b] = xi[a] - ti; xr[a] += tr; xi[a] += ti;
        float ncr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = ncr;
      }
    }
  }
}

// 스펙트럼 → 특징값 (lo~hi Hz 에서 피크, bandLo 이상 에너지 비율 %)
void spectrumFeatures(int n, float fs, float lo, float hi, float bandLo, float& peakHz, float& energyPct) {
  float best = -1, pAll = 0, pBand = 0;
  for (int k = 1; k < n / 2; k++) {
    float f = k * fs / n;
    if (f < lo || f > hi) continue;
    float p = re[k] * re[k] + im[k] * im[k];
    pAll += p;
    if (f >= bandLo) pBand += p;
    if (p > best) { best = p; peakHz = f; }
  }
  energyPct = pAll > 0 ? 100.0 * pBand / pAll : 0;
}

// 스펙트럼 → 그래프용 막대 nb 칸 (0~fmax Hz 를 nb 칸으로 나눠 칸마다 가장 큰 크기, 가장 큰 칸 = 99).
// 특징값을 구한 범위(lo~hi Hz) 밖은 0 으로 둠 → 화면의 그래프와 판정이 같은 범위를 봄
void binSpectrum(int n, float fs, float lo, float hi, float fmax, uint8_t* out, int nb) {
  float tmp[64];
  for (int i = 0; i < nb; i++) tmp[i] = 0;
  float mx = 0, binW = fmax / nb;
  for (int k = 1; k < n / 2; k++) {
    float f = k * fs / n;
    if (f < lo || f > hi || f >= fmax) continue;
    float a = sqrtf(re[k] * re[k] + im[k] * im[k]);
    int b = (int)(f / binW);
    if (b >= nb) b = nb - 1;
    if (a > tmp[b]) tmp[b] = a;
    if (a > mx) mx = a;
  }
  for (int i = 0; i < nb; i++) out[i] = mx > 0 ? (uint8_t)(99.0f * tmp[i] / mx + 0.5f) : 0;
}

// ---------------- 솔레노이드 ----------------
void gateUpdate() {                      // 정해 둔 시간(STRIKE_MS)이 지나면 반드시 끔. 마이크를 읽을 때마다 불러서 측정 중에도 꺼짐
  if (gateOn && (long)(millis() - gateOffAt) >= 0) { digitalWrite(MOSFET_GATE, LOW); gateOn = false; }
}
void doStrike() {                        // 솔레노이드로 타격 + 측정 1회 준비
  if (gateOn || millis() - lastStrike < STRIKE_MIN_GAP_MS) { Serial.println("# 너무 빨라요. 잠시 뒤 다시 누르세요"); return; }
  lastStrike = millis();
  armed = true;
  armUntil = millis() + STRIKE_WAIT_MS;
  gateOn = true;
  gateOffAt = millis() + STRIKE_MS;
  digitalWrite(MOSFET_GATE, HIGH);
  Serial.println("# 타격!");
}
void doHandArm() {                       // 손으로 칠 때: 소리를 기다림
  armed = true;
  armUntil = millis() + HAND_WAIT_MS;
  Serial.println("# 측정 대기: 지금 볼트를 한 번 치세요 (8초)");
}

// ---------------- MPU6050 (진동) ----------------
void mpuWrite(uint8_t reg, uint8_t v) { Wire.beginTransmission(0x68); Wire.write(reg); Wire.write(v); Wire.endTransmission(); }
bool mpuReadG(float& g) {
  Wire.beginTransmission(0x68); Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(0x68, 6) != 6) return false;
  int16_t ax = (Wire.read() << 8) | Wire.read(), ay = (Wire.read() << 8) | Wire.read(), az = (Wire.read() << 8) | Wire.read();
  g = sqrtf((float)ax * ax + (float)ay * ay + (float)az * az) / 2048.0;   // ±16 g 범위 → 2048 = 1 g
  return true;
}
void mpuTask(void*) {                   // 1 ms 마다 가속도 크기를 원형 버퍼에 저장 (코어 0 에서 따로 돎)
  TickType_t last = xTaskGetTickCount();
  for (;;) {
    float g;
    if (mpuReadG(g)) { accBuf[accIdx % ACC_N] = g; accIdx++; accLast = g; }
    vTaskDelayUntil(&last, 1);
  }
}
bool mpuBegin() {
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  Wire.beginTransmission(0x68);
  if (Wire.endTransmission() != 0) return false;
  mpuWrite(0x6B, 0x00);                 // 잠 깨우기
  mpuWrite(0x1A, 0x00);                 // 저역 필터 260 Hz (가장 넓게)
  mpuWrite(0x19, 0x00);                 // 샘플링 분주 0
  mpuWrite(0x1C, 0x18);                 // 가속도 ±16 g
  delay(50);
  xTaskCreatePinnedToCore(mpuTask, "mpu", 3072, NULL, 2, NULL, 0);
  return true;
}

// ---------------- INMP441 (마이크) ----------------
void micBegin() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  cfg.sample_rate = FS;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;    // 양쪽 다 읽고 신호 있는 쪽을 씀 (L/R 배선 실수에도 동작)
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = BLK;
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = PIN_SCK;
  pins.ws_io_num = PIN_WS;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = PIN_SD;
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  gpio_pulldown_en((gpio_num_t)PIN_SD);   // 마이크가 안 꽂혀 있으면 0 이 읽히게 (INMP441 데이터시트도 풀다운 권장)
}
// 한 블록(256 샘플) 읽어서 -1~1 로 바꾸고, 최대 크기를 돌려줌
float micRead(float* out) {
  size_t got = 0;
  i2s_read(I2S_NUM_0, raw, sizeof(raw), &got, portMAX_DELAY);
  gateUpdate();                          // 솔레노이드 끄는 시간 확인 (측정하는 동안에도 불림)
  float mean = 0;
  for (int i = 0; i < BLK; i++) {
    int32_t l = raw[2 * i] >> 8, r = raw[2 * i + 1] >> 8;     // 24비트 값
    out[i] = (abs(l) > abs(r) ? l : r) / 8388608.0;
    if (raw[2 * i] != 0 || raw[2 * i + 1] != 0) micNonZero++;
    mean += out[i];
  }
  mean /= BLK;
  float pk = 0;
  for (int i = 0; i < BLK; i++) { out[i] -= mean; pk = max(pk, fabsf(out[i])); }
  return pk;
}

// ---------------- 판정 LED ----------------
// 정상(OK)=초록 켜짐 / 재측정(CHECK)=빨강 깜빡임 / 체결 이상 의심(NG)=빨강 켜짐 / OFF=끔
// 명령은 "L,OK" "L,CHECK" "L,NG" "L,OFF" 한 줄. 폰은 블루투스(RX_UUID)로, PC 대시보드는 USB 시리얼로 보냄.
enum LedMode { LED_OFF_M, LED_OK_M, LED_CHECK_M, LED_NG_M };
volatile LedMode ledMode = LED_OFF_M;
volatile unsigned long ledSince = 0;

void ledCommand(const char* s) {           // s = "OK" / "CHECK" / "NG" / "OFF" (앞의 "L," 은 뺀 것)
  LedMode m = LED_OFF_M;
  if (!strcmp(s, "OK")) m = LED_OK_M;
  else if (!strcmp(s, "CHECK")) m = LED_CHECK_M;
  else if (!strcmp(s, "NG")) m = LED_NG_M;
  else if (strcmp(s, "OFF")) return;       // 모르는 글자는 무시
  ledMode = m;
  ledSince = millis();
}

void ledUpdate() {                         // loop 에서 자주 불러 줌 (기다리지 않음)
  LedMode m = ledMode;
  if (m != LED_OFF_M && LED_HOLD_MS > 0 && millis() - ledSince > LED_HOLD_MS) { ledMode = m = LED_OFF_M; }
  bool g = (m == LED_OK_M);
  bool r = (m == LED_NG_M) || (m == LED_CHECK_M && ((millis() - ledSince) / LED_BLINK_MS) % 2 == 0);
  digitalWrite(PIN_LED_GREEN, g ? HIGH : LOW);
  digitalWrite(PIN_LED_RED, r ? HIGH : LOW);
}

void ledBegin() {
  pinMode(PIN_GND_GREEN, OUTPUT); pinMode(PIN_GND_RED, OUTPUT);       // 가짜 GND 먼저 LOW 로 고정
  digitalWrite(PIN_GND_GREEN, LOW); digitalWrite(PIN_GND_RED, LOW);
  pinMode(PIN_LED_GREEN, OUTPUT); pinMode(PIN_LED_RED, OUTPUT);
  digitalWrite(PIN_LED_GREEN, HIGH); delay(250); digitalWrite(PIN_LED_GREEN, LOW);   // 켜질 때 한 번씩 깜빡여서 배선 확인
  digitalWrite(PIN_LED_RED, HIGH);   delay(250); digitalWrite(PIN_LED_RED, LOW);
}

// ---------------- 보내기 (USB + BLE) ----------------
BLECharacteristic* ch = nullptr;
bool bleConnected = false;
class RxCB : public BLECharacteristicCallbacks {      // 폰이 보낸 글자를 받음: "L,OK" (LED), "S" (타격), "M" (손으로 칠게요)
  void onWrite(BLECharacteristic* c) override {
    auto raw = c->getValue();                             // 코어 버전에 따라 std::string 또는 String
    String v = String(raw.c_str());
    v.trim();
    if (v.startsWith("L,")) ledCommand(v.c_str() + 2);
    else if (v == "S") reqStrike = true;                  // 여기서 바로 솔레노이드를 켜지 않고 loop 가 처리
    else if (v == "M") reqHand = true;
  }
};
class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { bleConnected = true; Serial.println("# BLE 연결됨"); }
  void onDisconnect(BLEServer*) override { bleConnected = false; Serial.println("# BLE 끊김"); BLEDevice::startAdvertising(); }
};

void sendLine(const char* s) {            // 한 줄을 USB 와 블루투스로 보냄 (블루투스는 20바이트씩 쪼개서)
  Serial.println(s);
  digitalWrite(LED_BUILTIN, HIGH); delay(60); digitalWrite(LED_BUILTIN, LOW);
  if (bleConnected && ch) {
    static char buf[640];
    snprintf(buf, sizeof(buf), "%s\n", s);
    size_t len = strlen(buf);
    for (size_t i = 0; i < len; i += 20) {
      size_t n = (len - i < 20) ? (len - i) : 20;
      ch->setValue((uint8_t*)buf + i, n);
      ch->notify();
      delay(10);
    }
  }
}
void publish() { sendLine(lastMsg); }

// 숫자 배열을 ,"키":[1,2,3] 모양으로 이어 붙임 (돌려주는 값 = 새 글자 길이)
int appendArr(char* b, size_t cap, int n, const char* key, const uint8_t* a, int cnt) {
  n += snprintf(b + n, cap - n, ",\"%s\":[", key);
  for (int i = 0; i < cnt && n < (int)cap - 8; i++) n += snprintf(b + n, cap - n, "%s%u", i ? "," : "", (unsigned)a[i]);
  n += snprintf(b + n, cap - n, "]");
  return n;
}

// ---------------- 실제 타격 측정 ----------------
void measureHit(unsigned long tTrig) {
  // 1) 녹음: 직전 블록 + 방금 블록 + 이어서 11 블록
  memcpy(cap, prevBlk, sizeof(prevBlk));
  memcpy(cap + BLK, curBlk, sizeof(curBlk));
  for (int b = 2; b < CAP_N / BLK; b++) micRead(cap + b * BLK);
  // 2) 타격 시작점 찾기 (최대값의 30% 를 처음 넘는 곳 5 ms 전부터)
  float pk = 0;
  for (int i = 0; i < CAP_N; i++) pk = max(pk, fabsf(cap[i]));
  int hit = 0;
  while (hit < CAP_N && fabsf(cap[hit]) < pk * 0.3) hit++;
  int start = max(0, hit - FS / 200);
  int n = min(SEG_N, CAP_N - start);
  float mm = 0;
  for (int i = 0; i < NFFT; i++) {
    if (i < n) {
      float w = 0.5 - 0.5 * cos(2 * PI * i / (n - 1));    // 해닝 창
      mm = max(mm, fabsf(cap[start + i]));
      re[i] = cap[start + i] * w;
    } else re[i] = 0;
    im[i] = 0;
  }
  fft(re, im, NFFT);
  float mf = 0, me = 0;
  spectrumFeatures(NFFT, FS, 200, 10000, 2000, mf, me);
  binSpectrum(NFFT, FS, 200, 10000, SP_MIC_FMAX, spMic, SP_MIC_N);   // 진동 FFT 가 re/im 을 덮어쓰기 전에 그래프용 막대를 뽑아 둠
  mm = min(mm, 1.0f);

  // 3) 진동: 타격 후 200 ms 가 지난 뒤, 최근 256 ms 를 가져와 분석
  bool haveAcc = false;
  float af = 0, am = 0, ae = 0;
  if (mpuOk) {
    while (millis() - tTrig < 200) { gateUpdate(); delay(1); }
    uint32_t end = accIdx;
    if (end >= ACC_SEG) {
      float mean = 0;
      for (int j = 0; j < ACC_SEG; j++) mean += accBuf[(end - ACC_SEG + j) % ACC_N];
      mean /= ACC_SEG;
      for (int j = 0; j < ACC_SEG; j++) {
        float x = accBuf[(end - ACC_SEG + j) % ACC_N] - mean;
        am = max(am, fabsf(x));
        re[j] = x * (0.5 - 0.5 * cos(2 * PI * j / (ACC_SEG - 1)));
        im[j] = 0;
      }
      fft(re, im, ACC_SEG);
      spectrumFeatures(ACC_SEG, ACC_FS, 20, 475, 100, af, ae);
      binSpectrum(ACC_SEG, ACC_FS, 20, 475, SP_ACC_FMAX, spAcc, SP_ACC_N);
      haveAcc = true;
    }
  }
  seq++;
  int len = snprintf(lastMsg, sizeof(lastMsg),
                     "{\"v\":2,\"seq\":%lu,\"k\":\"%08lx-%lu\",\"src\":\"mic\",\"mf\":%.1f,\"mm\":%.3f,\"me\":%.1f",
                     seq, (unsigned long)bootId, seq, mf, mm, me);
  if (haveAcc) len += snprintf(lastMsg + len, sizeof(lastMsg) - len, ",\"af\":%.1f,\"am\":%.3f,\"ae\":%.1f", af, am, ae);
  len = appendArr(lastMsg, sizeof(lastMsg), len, "sm", spMic, SP_MIC_N);
  if (haveAcc) len = appendArr(lastMsg, sizeof(lastMsg), len, "sa", spAcc, SP_ACC_N);
  snprintf(lastMsg + len, sizeof(lastMsg) - len, "}");
  publish();
}

// ---------------- setup / loop ----------------
void setup() {
  pinMode(FAKE_GND_MIC_LR, OUTPUT);       // 마이크 L/R 을 LOW 로 고정 (= GND 처럼)
  digitalWrite(FAKE_GND_MIC_LR, LOW);
  pinMode(MOSFET_GATE, OUTPUT);           // 솔레노이드는 켜질 때부터 꺼진 상태로 시작
  digitalWrite(MOSFET_GATE, LOW);
  Serial.begin(115200);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  ledBegin();
  delay(300);
  bootId = esp_random();
  Serial.println("# tap_sensor_v2 시작");
  BLEDevice::init(NAME);
  BLEServer* srv = BLEDevice::createServer();
  srv->setCallbacks(new ServerCB());
  BLEService* svc = srv->createService(SERVICE_UUID);
  ch = svc->createCharacteristic(CHAR_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  ch->addDescriptor(new BLE2902());
  BLECharacteristic* rx = svc->createCharacteristic(RX_UUID, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCB());
  svc->start();
  BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
  BLEDevice::startAdvertising();
  Serial.printf("# BLE 광고 시작: %s\n", NAME);
  // 블루투스를 먼저 켠 다음, 남은 메모리에서 분석용 버퍼를 받음
  cap = (float*)malloc(sizeof(float) * CAP_N);
  re = (float*)malloc(sizeof(float) * NFFT);
  im = (float*)malloc(sizeof(float) * NFFT);
  accBuf = (float*)calloc(ACC_N, sizeof(float));
  if (!cap || !re || !im || !accBuf) {
    Serial.println("# 메모리 부족! Partition Scheme 를 'Huge APP' 으로 바꿔 다시 올리세요.");
    while (true) delay(1000);
  }
  mpuOk = mpuBegin();
  Serial.println(mpuOk ? "# MPU6050 OK" : "# MPU6050 없음 → 배선 확인 (SDA 21, SCL 22, VCC 3.3V). 진동 값 없이 동작");
  micBegin();
  micNonZero = 0;
  for (int i = 0; i < 40; i++) micRead(curBlk);          // 약 0.3초 동안 마이크 확인 + 소음 측정
  micOk = micNonZero > 40 * BLK / 2;                     // 절반 넘게 값이 들어와야 마이크가 있는 것
  Serial.println(micOk ? "# INMP441 OK" : "# INMP441 없음 → 배선 확인 (WS 25, SCK 32, SD 33, L/R→GPIO27, VDD 3.3V). 측정 꺼짐");
  Serial.printf("# 남은 메모리 %u bytes\n", (unsigned)ESP.getFreeHeap());
#if AUTO_DETECT
  Serial.println("# 준비 완료 (AUTO_DETECT 켜짐: 소리가 나면 무조건 측정)");
#else
  Serial.println("# 준비 완료. 'S' = 솔레노이드 타격+측정, 'M' = 손으로 칠 때 측정 대기, BOOT 짧게 = 타격, 1초 꾹 = 측정 대기");
#endif
}

unsigned long lastDbg = 0;
float dbgPeak = 0;

void loop() {
  gateUpdate();
  // 폰/시리얼/버튼 명령 처리
  if (reqStrike) { reqStrike = false; doStrike(); }
  if (reqHand) { reqHand = false; doHandArm(); }
  // 마이크 한 블록 읽기 (8 ms)
  memcpy(prevBlk, curBlk, sizeof(curBlk));
  float pk = micRead(curBlk);
  dbgPeak = max(dbgPeak, pk);
  float trig = max(TRIG_MIN, noise * TRIG_X_NOISE);
  bool want = armed;
#if AUTO_DETECT
  want = true;
#endif
  if (armed && (long)(millis() - armUntil) > 0) {          // 기다리던 시간이 지났는데 소리가 없었음
    armed = false;
    Serial.println("# 소리를 못 들었어요 (타격이 약하거나 마이크가 멀어요)");
    sendLine("{\"v\":2,\"evt\":\"miss\"}");
  }
  if (micOk && want && pk > trig && millis() - lastTrig > COOLDOWN_MS) {
    armed = false;                                         // 1번 측정하면 끝 (다음 명령이 올 때까지 측정 안 함)
    lastTrig = millis();
    measureHit(lastTrig);
  } else {
    noise = 0.98 * noise + 0.02 * pk;                    // 평소 소음 크기를 천천히 따라감
  }
  // 배선 확인용 출력
  if (debugOn && millis() - lastDbg > 300) {
    Serial.printf("# 마이크 최대 %.4f (소음 %.4f, 타격 기준 %.4f) / 진동 %.3f g / %s\n", dbgPeak, noise, trig, accLast, armed ? "측정 대기 중" : "대기 안 함");
    dbgPeak = 0; lastDbg = millis();
  }
  ledUpdate();
  // 시리얼 글자 명령
  while (Serial.available()) {
    char c = Serial.read();
    static char cmd[10]; static int ci = -1;               // "L,OK\n" 같은 LED 명령 한 줄 받기
    if (ci < 0 && c == 'L') { ci = 0; continue; }
    if (ci >= 0) {
      if (c == '\n' || c == '\r') { cmd[ci] = 0; if (cmd[0] == ',') ledCommand(cmd + 1); ci = -1; }
      else if (ci < 9) cmd[ci++] = c;
      else ci = -1;
      continue;
    }
    if (c == 'd' || c == 'D') { debugOn = !debugOn; Serial.println(debugOn ? "# 센서 값 보기 켬" : "# 센서 값 보기 끔"); }
    else if (c == 'S' || c == 's') doStrike();
    else if (c == 'M' || c == 'm') doHandArm();
  }
  // BOOT 버튼(또는 GPIO0-GND 스위치): 짧게 = 솔레노이드 타격, 1초 꾹 = 손으로 칠 때 측정 대기
  if (digitalRead(BOOT_PIN) == LOW) {
    unsigned long t0 = millis();
    while (digitalRead(BOOT_PIN) == LOW && millis() - t0 < 1500) { gateUpdate(); delay(5); }
    unsigned long held = millis() - t0;
    while (digitalRead(BOOT_PIN) == LOW) { gateUpdate(); delay(5); }
    i2s_zero_dma_buffer(I2S_NUM_0);
    if (held >= 1000) doHandArm();
    else if (held > 30) doStrike();
  }
}
