// tap_sensor_v2.ino - 실제 센서(INMP441 마이크 + MPU6050 진동)로 타격음을 재고, 특징값을 무선으로 보내는 펌웨어
// 보드: ESP32-DevKitC V4 (ESP32-WROOM-32E)  /  Arduino 보드 선택: ESP32 Dev Module
// 권장: 도구(Tools) → Partition Scheme → "Huge APP (3MB No OTA/1MB SPIFFS)"  (USE_BLE 1 로 블루투스까지 켜면 꼭 필요)
// 추가 라이브러리 설치 필요 없음 (FFT 도 이 파일 안에 있음)
//
// ---------------- 배선 ----------------
//  INMP441  VDD→3.3V  GND→GND  L/R→GND  WS→GPIO25  SCK→GPIO32  SD→GPIO33
//  MPU6050  VCC→3.3V  GND→GND  SDA→GPIO21  SCL→GPIO22  (AD0, INT 는 연결 안 함)
//
// ---------------- 동작 ----------------
//  - 마이크가 큰 소리(타격)를 들으면 자동으로 100 ms 녹음 → FFT → 특징값 3개 (음향)
//    같은 순간의 진동(MPU6050, 1 kHz) 256 ms → FFT → 특징값 3개 (진동)
//  - 결과 한 줄(메시지 v2)을 USB 시리얼 + Wi-Fi(SoftAP) 로 보냄 (USE_BLE 1 이면 블루투스로도)
//      {"v":2,"seq":순번,"src":"mic","mf":음향피크Hz,"mm":음향크기,"me":음향고주파%,"af":진동피크Hz,"am":진동크기g,"ae":진동고주파%}
//  - 계산 방식은 PC 의 tools/audio_features.py 와 같음 (200 Hz~10 kHz 피크, 최대 진폭, 2~10 kHz 에너지 비율)
//  - 테스트용: BOOT 짧게 = 가짜 타격(src:"sim"), BOOT 1초 꾹 = 가짜 상태 바꾸기
//  - 시리얼 모니터 글자: d = 센서 값 계속 보기(배선 확인용) / t = 가짜 타격 / 1 2 3 = 가짜 상태
//  - Wi-Fi: 이름 TAP-01, 비밀번호 bolt1234, 주소 http://192.168.4.1   (/latest = 최근 측정 JSON)
//  - 판정 LED: 초록(정상) / 빨강 깜빡임(재측정) / 빨강(체결 이상 의심). 핀·배선은 PIN_LED_* 참고. 폰(블루투스 쓰기)·PC(USB "L,OK")가 판정 결과를 보내 줌
//  - BLE: 이름 TAP-01 (web/index.html 과 같은 UUID, 20바이트씩 나눠 보내고 줄바꿈으로 끝)

#define USE_WIFI 0          // Wi-Fi(SoftAP) 쓰기 (1 로 하면 켬). 블루투스와 같이 켜면 메모리 부족이라 지금은 끔.
#define USE_BLE  1          // 블루투스 쓰기 (0 으로 하면 끔). 폰 앱으로 쓰므로 켬.
                            // Wi-Fi + 블루투스를 같이 켜면 메모리가 모자라 재부팅될 수 있어 나중에 따로 시험

#include <Wire.h>
#include "driver/i2s.h"
#include "driver/gpio.h"
#if USE_WIFI
#include <WiFi.h>
#include <WebServer.h>
#endif
#if USE_BLE
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>
#endif

// ---------------- 설정 ----------------
const char* NAME = "TAP-01";            // Wi-Fi 이름 = BLE 이름 (장치마다 TAP-01, TAP-02 ...)
const char* PASS = "bolt1234";          // Wi-Fi 비밀번호 (8자 이상)
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHAR_UUID    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   // 측정값 보내는 통로 (ESP32 → 폰, notify)
#define RX_UUID      "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   // 판정 받는 통로 (폰 → ESP32, write) : LED 켜기용
#define PIN_WS 25
#define PIN_SCK 32
#define PIN_SD 33
#define PIN_SDA 21
#define PIN_SCL 22
#define BOOT_PIN 0
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
const unsigned long COOLDOWN_MS = 600;  // 한 번 친 뒤 다시 감지하기까지 쉬는 시간
const int   ACC_FS = 1000, ACC_N = 1024, ACC_SEG = 256;

// ---------------- 상태 ----------------
float *cap, *re, *im, *accBuf;          // 큰 버퍼는 무선을 켠 뒤에 메모리를 받음 (setup 참고)
volatile uint32_t accIdx = 0;
float accLast = 0;
bool mpuOk = false, micOk = false, debugOn = false;
uint32_t micNonZero = 0;
float noise = 0.005;
unsigned long lastTrig = 0, seq = 0;
int simState = 0;
const char* SIM_KO[] = {"정상", "재측정", "이상"};
char lastMsg[200] = "{\"v\":2,\"seq\":0}";
int32_t raw[BLK * 2];
float prevBlk[BLK], curBlk[BLK];

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

// ---------------- 보내기 (USB + Wi-Fi + BLE) ----------------
#if USE_WIFI
WebServer server(80);
#endif
#if USE_BLE
BLECharacteristic* ch = nullptr;
bool bleConnected = false;
class RxCB : public BLECharacteristicCallbacks {      // 폰이 보낸 "L,OK" 같은 글자를 받음
  void onWrite(BLECharacteristic* c) override {
    auto raw = c->getValue();                             // 코어 버전에 따라 std::string 또는 String
    String v = String(raw.c_str());
    v.trim();
    if (v.startsWith("L,")) ledCommand(v.c_str() + 2);
  }
};
class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { bleConnected = true; Serial.println("# BLE 연결됨"); }
  void onDisconnect(BLEServer*) override { bleConnected = false; Serial.println("# BLE 끊김"); BLEDevice::startAdvertising(); }
};
#endif

void publish() {
  Serial.println(lastMsg);
  digitalWrite(LED_BUILTIN, HIGH); delay(60); digitalWrite(LED_BUILTIN, LOW);
#if USE_BLE
  if (bleConnected && ch) {
    char buf[210];
    snprintf(buf, sizeof(buf), "%s\n", lastMsg);
    size_t len = strlen(buf);
    for (size_t i = 0; i < len; i += 20) {
      size_t n = (len - i < 20) ? (len - i) : 20;
      ch->setValue((uint8_t*)buf + i, n);
      ch->notify();
      delay(10);
    }
  }
#endif
}

// ---------------- 실제 타격 측정 ----------------
void measureHit(unsigned long tTrig) {
  // 1) 녹음: 직전 블록 + 방금 블록 + 이어서 11 블록
  memcpy(cap, prevBlk, sizeof(prevBlk));
  memcpy(cap + BLK, curBlk, sizeof(curBlk));
  for (int b = 2; b < CAP_N / BLK; b++) micRead(cap + b * BLK);
  // 2) 타격 시작점 찾기 (최대값의 30% 를 처음 넘는 곳 5 ms 전부터) - PC audio_features.py 와 같음
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
  mm = min(mm, 1.0f);

  // 3) 진동: 타격 후 200 ms 가 지난 뒤, 최근 256 ms 를 가져와 분석
  bool haveAcc = false;
  float af = 0, am = 0, ae = 0;
  if (mpuOk) {
    while (millis() - tTrig < 200) delay(1);
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
      haveAcc = true;
    }
  }
  seq++;
  if (haveAcc)
    snprintf(lastMsg, sizeof(lastMsg),
             "{\"v\":2,\"seq\":%lu,\"src\":\"mic\",\"mf\":%.1f,\"mm\":%.3f,\"me\":%.1f,\"af\":%.1f,\"am\":%.3f,\"ae\":%.1f}",
             seq, mf, mm, me, af, am, ae);
  else
    snprintf(lastMsg, sizeof(lastMsg), "{\"v\":2,\"seq\":%lu,\"src\":\"mic\",\"mf\":%.1f,\"mm\":%.3f,\"me\":%.1f}",
             seq, mf, mm, me);
  publish();
}

// ---------------- 가짜 타격 (테스트용, tools/sim.py 와 같은 값) ----------------
double gauss(double m, double s) {
  double u1 = (esp_random() + 1.0) / 4294967297.0, u2 = esp_random() / 4294967296.0;
  return m + s * sqrt(-2.0 * log(u1)) * cos(2 * PI * u2);
}
void simTap() {
  double f[6];
  if (simState == 0)      { f[0]=gauss(3200,65); f[1]=gauss(.80,.025); f[2]=gauss(69,2); f[3]=gauss(420,7);  f[4]=gauss(.71,.025); f[5]=gauss(72,2); }
  else if (simState == 2) { f[0]=gauss(3820,90); f[1]=gauss(.53,.03);  f[2]=gauss(43,3); f[3]=gauss(335,12); f[4]=gauss(.47,.03);  f[5]=gauss(47,3); }
  else                    { f[0]=gauss(3440,35); f[1]=gauss(.72,.03);  f[2]=gauss(57,2); f[3]=gauss(445,6);  f[4]=gauss(.62,.025); f[5]=gauss(60,2); }
  seq++;
  snprintf(lastMsg, sizeof(lastMsg),
           "{\"v\":2,\"seq\":%lu,\"src\":\"sim\",\"mf\":%.1f,\"mm\":%.3f,\"me\":%.1f,\"af\":%.1f,\"am\":%.3f,\"ae\":%.1f}",
           seq, f[0], max(f[1], 0.0), constrain(f[2], 0.0, 100.0), f[3], max(f[4], 0.0), constrain(f[5], 0.0, 100.0));
  publish();
}
void setSim(int s) { simState = constrain(s, 0, 2); Serial.printf("# 가짜 상태 = %s\n", SIM_KO[simState]); }

// ---------------- Wi-Fi 웹 화면 ----------------
#if USE_WIFI
const char PAGE[] = R"HTML(<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TAP-01</title>
<style>body{font-family:sans-serif;margin:16px;max-width:520px}button{font-size:17px;padding:10px 14px;margin:4px}
pre{background:#f2f4f7;padding:12px;border-radius:8px;white-space:pre-wrap}</style></head><body>
<h2>TAP-01 타음 센서</h2><p id="s">-</p><p>볼트를 치면 자동으로 측정돼요.</p>
<h3>최근 측정</h3><pre id="m">-</pre>
<p>테스트: <button onclick="go('/tap')">가짜 타격</button>
<button onclick="go('/state?s=1')">정상</button><button onclick="go('/state?s=2')">재측정</button><button onclick="go('/state?s=3')">이상</button></p>
<script>
async function go(u){await fetch(u);load();}
async function load(){try{const j=await (await fetch('/latest')).json();
document.getElementById('m').textContent=JSON.stringify(j.msg,null,1);
document.getElementById('s').textContent='마이크 '+(j.mic?'OK':'신호 없음')+' / 진동 '+(j.mpu?'OK':'없음')+' / 가짜 상태 '+j.sim;}catch(e){}}
setInterval(load,1000);load();
</script></body></html>)HTML";
void sendLatest() {
  char buf[300];
  snprintf(buf, sizeof(buf), "{\"mic\":%s,\"mpu\":%s,\"sim\":\"%s\",\"msg\":%s}",
           micOk ? "true" : "false", mpuOk ? "true" : "false", SIM_KO[simState], lastMsg);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", buf);
}
#endif

// ---------------- setup / loop ----------------
void setup() {
  Serial.begin(115200);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  ledBegin();
  delay(300);
  Serial.println("# tap_sensor_v2 시작");
#if USE_BLE
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
#endif
#if USE_WIFI
  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(NAME, PASS);
  Serial.printf("# Wi-Fi %s (비밀번호 %s) %s, 주소 http://", NAME, PASS, ok ? "켜짐" : "실패");
  Serial.println(WiFi.softAPIP());
  server.on("/", []() { server.send(200, "text/html; charset=utf-8", PAGE); });
  server.on("/latest", sendLatest);
  server.on("/tap", []() { simTap(); sendLatest(); });
  server.on("/state", []() { if (server.hasArg("s")) setSim(server.arg("s").toInt() - 1); sendLatest(); });
  server.begin();
#endif
  // 무선을 먼저 켠 다음, 남은 메모리에서 분석용 버퍼를 받음
  cap = (float*)malloc(sizeof(float) * CAP_N);
  re = (float*)malloc(sizeof(float) * NFFT);
  im = (float*)malloc(sizeof(float) * NFFT);
  accBuf = (float*)calloc(ACC_N, sizeof(float));
  if (!cap || !re || !im || !accBuf) {
    Serial.println("# 메모리 부족! USE_BLE 를 0 으로 하고 다시 올리세요.");
    while (true) delay(1000);
  }
  mpuOk = mpuBegin();
  Serial.println(mpuOk ? "# MPU6050 OK" : "# MPU6050 없음 → 배선 확인 (SDA 21, SCL 22, VCC 3.3V). 진동 값 없이 동작");
  micBegin();
  micNonZero = 0;
  for (int i = 0; i < 40; i++) micRead(curBlk);          // 약 0.3초 동안 마이크 확인 + 소음 측정
  micOk = micNonZero > 40 * BLK / 2;                     // 절반 넘게 값이 들어와야 마이크가 있는 것
  Serial.println(micOk ? "# INMP441 OK" : "# INMP441 없음 → 배선 확인 (WS 25, SCK 32, SD 33, L/R GND, VDD 3.3V). 자동 타격 감지 꺼짐");
  Serial.printf("# 남은 메모리 %u bytes\n", (unsigned)ESP.getFreeHeap());
  Serial.println("# 준비 완료. 볼트를 치세요. (시리얼 글자: d=센서값 보기, t=가짜 타격, 1/2/3=가짜 상태, L,OK / L,CHECK / L,NG / L,OFF = 판정 LED)");
}

unsigned long lastDbg = 0;
float dbgPeak = 0;

void loop() {
#if USE_WIFI
  server.handleClient();
#endif
  // 마이크 한 블록 읽기 (8 ms)
  memcpy(prevBlk, curBlk, sizeof(curBlk));
  float pk = micRead(curBlk);
  dbgPeak = max(dbgPeak, pk);
  float trig = max(TRIG_MIN, noise * TRIG_X_NOISE);
  if (micOk && pk > trig && millis() - lastTrig > COOLDOWN_MS) {   // 마이크가 없으면 자동 감지 안 함
    lastTrig = millis();
    measureHit(lastTrig);
  } else {
    noise = 0.98 * noise + 0.02 * pk;                    // 평소 소음 크기를 천천히 따라감
  }
  // 배선 확인용 출력
  if (debugOn && millis() - lastDbg > 300) {
    Serial.printf("# 마이크 최대 %.4f (소음 %.4f, 타격 기준 %.4f) / 진동 %.3f g\n", dbgPeak, noise, trig, accLast);
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
    else if (c == 't' || c == 'T') simTap();
    else if (c >= '1' && c <= '3') setSim(c - '1');
  }
  // BOOT 버튼: 짧게 = 가짜 타격, 1초 꾹 = 가짜 상태 바꾸기
  if (digitalRead(BOOT_PIN) == LOW) {
    unsigned long t0 = millis();
    while (digitalRead(BOOT_PIN) == LOW && millis() - t0 < 1500) delay(5);
    if (millis() - t0 >= 1000) setSim((simState + 1) % 3);
    else if (millis() - t0 > 30) simTap();
    while (digitalRead(BOOT_PIN) == LOW) delay(5);
    i2s_zero_dma_buffer(I2S_NUM_0);
  }
}
