// tap_wifi_v2.ino - ESP32 가 자체 Wi-Fi(SoftAP)를 만들고, 타음 특징값(메시지 v2)을 Wi-Fi 로 넘기는 펌웨어
// 대상 보드: ESP32-DevKitC V4 (ESP32-WROOM-32E)  /  Arduino 보드 선택: ESP32 Dev Module
//
// 조원 문서(SoftAP 예제)를 바탕으로, 우리 프로젝트용으로 늘린 것:
//   1) Wi-Fi 이름 TAP-01 / 비밀번호 bolt1234 로 ESP32 가 직접 Wi-Fi 를 만듦 (인터넷·공유기 필요 없음)
//   2) 주소 http://192.168.4.1
//        /         휴대폰·PC 브라우저용 화면 (최근 측정값 + [타격] [상태] 버튼)
//        /latest   최근 측정 1건 JSON  → PC 타음 검사 화면(ESP32 Wi-Fi 모드)이 이걸 읽음
//        /tap      가짜 타격 1번 (센서 없을 때 테스트용)
//        /state?s=1|2|3   가짜 상태 바꾸기 (1 정상, 2 재측정, 3 이상)
//   3) 보드 BOOT 버튼: 짧게 = 타격, 1초 꾹 = 상태 바꾸기.  USB 시리얼에도 같은 줄을 출력
//
// 지금은 센서가 없어서 makeFake() 가 가짜 값을 만듦 (tools/sim.py 와 같은 분포).
// 센서(INMP441 마이크, MPU6050 진동)를 붙이면 makeFake() 자리만 실제 측정 코드로 바꾸면 됨. 나머지는 그대로.
//
// 메시지 (스키마 v1.2 의 v2 + 순번 seq):
//   {"v":2,"seq":순번,"mf":음향피크Hz,"mm":음향크기,"me":음향에너지%,"af":진동피크Hz,"am":진동크기,"ae":진동에너지%}

#include <WiFi.h>
#include <WebServer.h>

const char* SSID = "TAP-01";        // 만들 Wi-Fi 이름 (장치마다 TAP-01, TAP-02 ...)
const char* PASS = "bolt1234";      // 비밀번호 (8자 이상 필수)
#define BOOT_PIN 0                  // DevKitC V4 의 BOOT 버튼 (누르면 LOW)

WebServer server(80);
const char* STATE_KO[] = {"정상", "재측정", "이상"};
int state = 0;                      // 0 정상, 1 재측정, 2 이상
unsigned long seq = 0;              // 측정할 때마다 1씩 증가 → PC 가 "새 측정"을 알아챔
char lastMsg[160] = "{\"v\":2,\"seq\":0}";

double gauss(double m, double s) {
  double u1 = (esp_random() + 1.0) / 4294967297.0, u2 = esp_random() / 4294967296.0;
  return m + s * sqrt(-2.0 * log(u1)) * cos(2 * PI * u2);
}

// ===== 여기만 나중에 실제 센서 측정으로 바꾸면 됨 =====
void makeFake(double f[6]) {
  if (state == 0)      { f[0]=gauss(3200,65); f[1]=gauss(.80,.025); f[2]=gauss(69,2); f[3]=gauss(420,7);  f[4]=gauss(.71,.025); f[5]=gauss(72,2); }
  else if (state == 2) { f[0]=gauss(3820,90); f[1]=gauss(.53,.03);  f[2]=gauss(43,3); f[3]=gauss(335,12); f[4]=gauss(.47,.03);  f[5]=gauss(47,3); }
  else                 { f[0]=gauss(3440,35); f[1]=gauss(.72,.03);  f[2]=gauss(57,2); f[3]=gauss(445,6);  f[4]=gauss(.62,.025); f[5]=gauss(60,2); }
  f[1] = max(f[1], 0.0); f[4] = max(f[4], 0.0);
  f[2] = constrain(f[2], 0.0, 100.0); f[5] = constrain(f[5], 0.0, 100.0);
}

void doTap() {
  double f[6];
  makeFake(f);
  seq++;
  snprintf(lastMsg, sizeof(lastMsg),
           "{\"v\":2,\"seq\":%lu,\"mf\":%.1f,\"mm\":%.3f,\"me\":%.1f,\"af\":%.1f,\"am\":%.3f,\"ae\":%.1f}",
           seq, f[0], f[1], f[2], f[3], f[4], f[5]);
  Serial.println(lastMsg);
}

void setState(int s) {
  state = constrain(s, 0, 2);
  Serial.printf("# 가짜 상태 = %s\n", STATE_KO[state]);   // '#' 줄은 PC 화면이 무시
}

const char PAGE[] PROGMEM = R"HTML(<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TAP-01</title>
<style>body{font-family:sans-serif;margin:16px;max-width:520px}button{font-size:18px;padding:12px 16px;margin:4px}
pre{background:#f2f4f7;padding:12px;border-radius:8px;white-space:pre-wrap}#st{font-weight:bold}</style></head><body>
<h2>TAP-01 타음 센서</h2><p>가짜 상태: <span id="st">-</span></p>
<button onclick="go('/tap')">타격 (테스트)</button><br>
<button onclick="go('/state?s=1')">정상</button><button onclick="go('/state?s=2')">재측정</button><button onclick="go('/state?s=3')">이상</button>
<h3>최근 측정</h3><pre id="m">-</pre>
<script>
async function go(u){await fetch(u);load();}
async function load(){try{const r=await fetch('/latest');const j=await r.json();
document.getElementById('m').textContent=JSON.stringify(j.msg,null,1);document.getElementById('st').textContent=j.state;}catch(e){}}
setInterval(load,1000);load();
</script></body></html>)HTML";

void sendLatest() {
  char buf[220];
  snprintf(buf, sizeof(buf), "{\"state\":\"%s\",\"msg\":%s}", STATE_KO[state], lastMsg);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", buf);
}

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(SSID, PASS);
  Serial.printf("# Wi-Fi %s (%s) 만들기 %s, 주소 http://", SSID, PASS, ok ? "성공" : "실패");
  Serial.println(WiFi.softAPIP());                        // 기본 192.168.4.1
  server.on("/", []() { server.send(200, "text/html; charset=utf-8", PAGE); });
  server.on("/latest", sendLatest);
  server.on("/tap", []() { doTap(); sendLatest(); });
  server.on("/state", []() { if (server.hasArg("s")) setState(server.arg("s").toInt() - 1); sendLatest(); });
  server.begin();
  setState(0);
}

void loop() {
  server.handleClient();
  while (Serial.available()) {                           // 시리얼 글자: t = 타격, 1 2 3 = 상태
    char c = Serial.read();
    if (c == 't' || c == 'T') doTap();
    else if (c >= '1' && c <= '3') setState(c - '1');
  }
  if (digitalRead(BOOT_PIN) == LOW) {                    // BOOT 버튼
    unsigned long t0 = millis();
    while (digitalRead(BOOT_PIN) == LOW && millis() - t0 < 1500) { server.handleClient(); delay(5); }
    if (millis() - t0 >= 1000) setState((state + 1) % 3);
    else if (millis() - t0 > 30) doTap();
    while (digitalRead(BOOT_PIN) == LOW) delay(5);
    delay(50);
  }
}
