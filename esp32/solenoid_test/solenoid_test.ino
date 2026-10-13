// 트리거 연사 테스트
const int MOSFET_GATE = 23;   // MOSFET G
const int TRIG_PIN    = 19;   // 트리거 COM
const int TRIG_GND    = 18;   // 트리거 NO (가짜 GND)

const int ON_MS  = 30;                 // 한 번 칠 때 전기 넣는 시간
const int OFF_MS = 170;                // 다음 타격까지 쉬는 시간
const unsigned long MAX_HOLD_MS = 10000; // 최대 연속 10초
const int DEBOUNCE_MS = 20;            // 스위치 떨림 무시 시간

void setup() {
  pinMode(MOSFET_GATE, OUTPUT);
  digitalWrite(MOSFET_GATE, LOW);      // 시작하자마자 OFF
  pinMode(TRIG_GND, OUTPUT);
  digitalWrite(TRIG_GND, LOW);         // 18번 = 가짜 GND
  pinMode(TRIG_PIN, INPUT_PULLUP);     // 평소 HIGH, 누르면 LOW
  Serial.begin(115200);
  delay(500);
  Serial.println("연사 테스트 준비: 방아쇠 누르는 동안 연속 타격");
}

bool pressed() {
  if (digitalRead(TRIG_PIN) == HIGH) return false;
  delay(DEBOUNCE_MS);
  return digitalRead(TRIG_PIN) == LOW;
}

void loop() {
  if (!pressed()) return;

  unsigned long start = millis();
  int count = 0;
  Serial.println("연사 시작");

  while (digitalRead(TRIG_PIN) == LOW) {
    if (millis() - start > MAX_HOLD_MS) {
      Serial.println("5초 초과 - 자동 정지 (손 떼면 다시 가능)");
      break;
    }
    digitalWrite(MOSFET_GATE, HIGH);
    delay(ON_MS);
    digitalWrite(MOSFET_GATE, LOW);
    delay(OFF_MS);
    count++;
  }

  digitalWrite(MOSFET_GATE, LOW);
  Serial.print("연사 끝: ");
  Serial.print(count);
  Serial.println("발");

  while (digitalRead(TRIG_PIN) == LOW) delay(10);  // 손 뗄 때까지 대기
  delay(DEBOUNCE_MS);
}