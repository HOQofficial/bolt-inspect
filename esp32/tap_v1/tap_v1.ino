// tap_v1.ino - BLE 메시지 v1 송신 테스트 (스키마 v1.0)
// 지금은 3초마다 "가짜 타음 결과"를 보냅니다. 태블릿 연결이 확인되면
// sendResult() 를 실제 FFT 판정 코드(개발 가이드 ③) 뒤에 붙이면 됩니다.
//
// 필요: Arduino IDE 2 + 보드 "esp32 by Espressif" (BLE 라이브러리 포함)
// 보드 선택: ESP32 Dev Module

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>

#define DEVICE_NAME  "TAP-01"                                   // 장치마다 TAP-01, TAP-02 ...
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"     // web/index.html 과 같아야 함
#define CHAR_UUID    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

BLECharacteristic* ch;
bool connected = false;

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer* s) override { connected = true; Serial.println("태블릿 연결됨"); }
  void onDisconnect(BLEServer* s) override { connected = false; Serial.println("연결 끊김"); BLEDevice::startAdvertising(); }
};

// [v1.1 권장] 특징값 메시지 v2 (조원 V3 방식, 판정은 태블릿/PC 가 등록 기준으로 함):
//   {"v":2,"mf":음향피크Hz,"mm":음향크기,"me":음향에너지%,"af":진동피크Hz,"am":진동크기,"ae":진동에너지%}
//   USB 로 PC '타음 검사' 화면에 보낼 때는 Serial.println(한 줄) 이면 됨. BLE 도 아래 sendResult 처럼 20바이트씩.
// BLE 메시지 v1: {"v":1,"pk":피크Hz,"dc":감쇠ms,"sc":점수,"m":"rule"|"rf","r":"OK"|"CHECK"|"NG"}
void sendResult(double peakHz, double decayMs, double score, const char* model, const char* result) {
  char buf[96];
  snprintf(buf, sizeof(buf), "{\"v\":1,\"pk\":%.0f,\"dc\":%.1f,\"sc\":%.2f,\"m\":\"%s\",\"r\":\"%s\"}",
           peakHz, decayMs, score, model, result);
  Serial.println(buf);                          // 시리얼 모니터로도 확인
  if (!connected) return;
  // BLE 기본 설정에서는 한 번에 20바이트까지만 전송됨 -> 20바이트씩 잘라 보내고, 끝에 줄바꿈(\n)을 붙임.
  // 태블릿(web/index.html)이 줄바꿈이 올 때까지 이어 붙여서 한 메시지로 복원함.
  strncat(buf, "\n", sizeof(buf) - strlen(buf) - 1);
  size_t len = strlen(buf);
  for (size_t i = 0; i < len; i += 20) {
    size_t n = (len - i < 20) ? (len - i) : 20;
    ch->setValue((uint8_t*)buf + i, n);
    ch->notify();
    delay(10);
  }
}

void setup() {
  Serial.begin(115200);
  BLEDevice::init(DEVICE_NAME);
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());
  BLEService* svc = server->createService(SERVICE_UUID);
  ch = svc->createCharacteristic(CHAR_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  ch->addDescriptor(new BLE2902());
  svc->start();
  BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
  BLEDevice::startAdvertising();
  Serial.println("광고 시작: " DEVICE_NAME);
}

void loop() {
  // 가짜 결과 (테스트용)
  double peak = 3100 + random(-60, 60);
  double score = fabs(peak - 3100) / 40.0;
  sendResult(peak, 15.0, score, "rule", score < 3 ? "OK" : (score < 5 ? "CHECK" : "NG"));
  delay(3000);
}
