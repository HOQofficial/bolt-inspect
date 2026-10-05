// tap_sim_v2.ino - 센서 없이 ESP32 → PC(타음 검사 화면) 연결을 시험하는 "가짜 타음" 펌웨어
//
// 하는 일
//   - 보드의 BOOT 버튼을 짧게 누르면 = 볼트를 한 번 친 것으로 보고, 가짜 특징값(메시지 v2) 한 줄을 보냄
//   - BOOT 버튼을 1초 이상 꾹 누르면 = 가짜 상태 바꾸기 (정상 → 재측정 → 이상 → 정상 ...)
//   - 시리얼 모니터에서 글자로도 조작 가능:  t = 타격,  1 = 정상,  2 = 재측정,  3 = 이상
//   - USB(시리얼)와 BLE(이름 TAP-01) 둘 다로 같은 메시지를 보냄
//
// 메시지 v2 (스키마 v1.2, tools/schema_rules.py features_from_msg 와 같음)
//   {"v":2,"mf":음향피크Hz,"mm":음향크기,"me":음향에너지%,"af":진동피크Hz,"am":진동크기,"ae":진동에너지%}
//   값은 tools/sim.py 의 mock_features 와 같은 분포 → 센서가 오면 makeFake() 자리만 실제 측정으로 바꾸면 됨
//
// 필요: Arduino IDE 2 + 보드 패키지 "esp32 by Espressif Systems",  보드 선택: ESP32 Dev Module

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>

#define DEVICE_NAME  "TAP-01"
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"   // web/index.html 과 같음
#define CHAR_UUID    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
#define BOOT_PIN     0      // 대부분의 ESP32 DevKit 의 BOOT 버튼 (누르면 LOW)
#ifndef LED_BUILTIN
#define LED_BUILTIN  2      // 파란 LED 가 2번인 보드가 많음 (없으면 그냥 안 켜짐)
#endif

const char* STATE_KO[] = {"정상", "재측정", "이상"};
int state = 0;              // 0 정상, 1 재측정, 2 이상
BLECharacteristic* ch;
bool connected = false;

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { connected = true; Serial.println("# BLE 연결됨"); }
  void onDisconnect(BLEServer*) override { connected = false; Serial.println("# BLE 끊김"); BLEDevice::startAdvertising(); }
};

// 정규분포 난수 (평균 m, 표준편차 s)
double gauss(double m, double s) {
  double u1 = (esp_random() + 1.0) / 4294967297.0, u2 = esp_random() / 4294967296.0;
  return m + s * sqrt(-2.0 * log(u1)) * cos(2 * PI * u2);
}

// 가짜 특징값 만들기 (tools/sim.py 와 같은 값)
void makeFake(double f[6]) {
  if (state == 0)      { f[0]=gauss(3200,65); f[1]=gauss(.80,.025); f[2]=gauss(69,2); f[3]=gauss(420,7);  f[4]=gauss(.71,.025); f[5]=gauss(72,2); }
  else if (state == 2) { f[0]=gauss(3820,90); f[1]=gauss(.53,.03);  f[2]=gauss(43,3); f[3]=gauss(335,12); f[4]=gauss(.47,.03);  f[5]=gauss(47,3); }
  else                 { f[0]=gauss(3440,35); f[1]=gauss(.72,.03);  f[2]=gauss(57,2); f[3]=gauss(445,6);  f[4]=gauss(.62,.025); f[5]=gauss(60,2); }
  f[1] = max(f[1], 0.0); f[4] = max(f[4], 0.0);
  f[2] = constrain(f[2], 0.0, 100.0); f[5] = constrain(f[5], 0.0, 100.0);
}

void sendTap() {
  double f[6];
  makeFake(f);
  char buf[128];
  snprintf(buf, sizeof(buf), "{\"v\":2,\"mf\":%.1f,\"mm\":%.3f,\"me\":%.1f,\"af\":%.1f,\"am\":%.3f,\"ae\":%.1f}",
           f[0], f[1], f[2], f[3], f[4], f[5]);
  Serial.println(buf);                               // PC 타음 검사 화면은 이 한 줄을 읽음
  digitalWrite(LED_BUILTIN, HIGH); delay(80); digitalWrite(LED_BUILTIN, LOW);
  if (!connected) return;
  strncat(buf, "\n", sizeof(buf) - strlen(buf) - 1); // BLE: 20바이트씩 나눠 보내고 줄바꿈으로 끝
  size_t len = strlen(buf);
  for (size_t i = 0; i < len; i += 20) {
    size_t n = (len - i < 20) ? (len - i) : 20;
    ch->setValue((uint8_t*)buf + i, n);
    ch->notify();
    delay(10);
  }
}

void setState(int s) {
  state = s;
  Serial.printf("# 가짜 상태 = %s\n", STATE_KO[state]);   // '#' 로 시작하는 줄은 PC 화면이 무시함
  for (int i = 0; i <= state; i++) { digitalWrite(LED_BUILTIN, HIGH); delay(150); digitalWrite(LED_BUILTIN, LOW); delay(150); }
}

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  BLEDevice::init(DEVICE_NAME);
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());
  BLEService* svc = server->createService(SERVICE_UUID);
  ch = svc->createCharacteristic(CHAR_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  ch->addDescriptor(new BLE2902());
  svc->start();
  BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
  BLEDevice::startAdvertising();
  delay(300);
  Serial.println("# tap_sim_v2 시작. BOOT 짧게 = 타격, 1초 꾹 = 상태 바꾸기 / 글자: t 1 2 3");
  setState(0);
}

void loop() {
  // 시리얼 글자 명령
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 't' || c == 'T') sendTap();
    else if (c >= '1' && c <= '3') setState(c - '1');
  }
  // BOOT 버튼
  if (digitalRead(BOOT_PIN) == LOW) {
    unsigned long t0 = millis();
    while (digitalRead(BOOT_PIN) == LOW && millis() - t0 < 1500) delay(5);
    if (millis() - t0 >= 1000) setState((state + 1) % 3);
    else if (millis() - t0 > 30) sendTap();          // 30ms 미만은 잡음으로 무시
    while (digitalRead(BOOT_PIN) == LOW) delay(5);   // 손 뗄 때까지 대기
    delay(50);
  }
}
