// ESP32(TAP-xx) 블루투스 연결.
//  - 안드로이드 앱 안에서는 Capacitor 블루투스 플러그인을 쓰고,
//  - 크롬(PC·맥·안드로이드)에서는 Web Bluetooth 를 씀. 같은 화면 코드가 둘 다에서 돌아감.
// 메시지는 20바이트씩 나뉘어 오고 줄바꿈(\n)으로 끝남 (esp32/tap_sensor_v2 와 같은 규칙).
import { Capacitor } from "@capacitor/core";
import { BleClient } from "@capacitor-community/bluetooth-le";
import { LineAssembler } from "./lines.js";

export const SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
export const CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";
export const RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";   // 폰 → ESP32: 판정 LED 명령 ("L,OK" 등)
const LS_DEVICE = "tap_device_id_v1";

export const isNative = () => Capacitor.isNativePlatform();
export const bleSupported = () => isNative() || !!navigator.bluetooth;
export const hasSavedDevice = () => isNative() && !!safeGet(LS_DEVICE);
export function forgetDevice() { try { localStorage.removeItem(LS_DEVICE); } catch { /* 무시 */ } }

function safeGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function safeSet(k, v) { try { localStorage.setItem(k, v); } catch { /* 무시 */ } }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 하나의 연결을 관리. state: "idle" | "connecting" | "connected" | "reconnecting"
export class TapLink {
  constructor({ onLine, onState, onLog }) {
    this.onLine = onLine;
    this.onState = onState;
    this.onLog = onLog || (() => {});
    this.asm = new LineAssembler((l) => this.onLine(l));
    this.userStopped = true;
    this.deviceId = null;
    this.webDevice = null;
    this.rx = null;           // Web Bluetooth 쓰기 통로
    this._ledWarned = false;
  }

  // 판정 결과를 ESP32 에 보내 LED 를 켬. result = "OK" | "CHECK" | "NG" | "OFF". 실패해도 앱 동작에는 영향 없음.
  async sendLed(result) {
    if (this.state !== "connected") return;
    const bytes = new TextEncoder().encode(`L,${result}\n`);
    try {
      if (isNative()) {
        await BleClient.write(this.deviceId, SERVICE_UUID, RX_UUID, new DataView(bytes.buffer));
      } else if (this.rx) {
        if (this.rx.writeValueWithResponse) await this.rx.writeValueWithResponse(bytes);   // 응답을 받는 쓰기가 더 확실함
        else await this.rx.writeValue(bytes);
      } else {
        this.onLog("LED 통로가 없어요 → ESP32 에 LED 포함 펌웨어를 올렸는지, 폰 블루투스를 껐다 켠 뒤 다시 연결해 보세요");
        return;
      }
      this.onLog(`LED 명령 보냄: ${result}`);
    } catch (e) {
      this.onLog(`LED 명령 실패: ${e.message || e}`);
    }
  }

  async connect({ pick = false } = {}) {
    if (!bleSupported()) throw new Error("이 브라우저는 블루투스를 지원하지 않아요. 안드로이드 앱이나 크롬을 사용하세요.");
    this.userStopped = false;
    this.onState("connecting");
    try {
      if (isNative()) await this._connectNative(pick);
      else await this._connectWeb();
      this.onState("connected");
    } catch (e) {
      this.userStopped = true;
      this.onState("idle");
      throw e;
    }
  }

  async _connectNative(pick) {
    await BleClient.initialize();
    let id = pick ? null : safeGet(LS_DEVICE);
    if (!id) {
      const d = await BleClient.requestDevice({ namePrefix: "TAP-", optionalServices: [SERVICE_UUID] });
      id = d.deviceId;
      safeSet(LS_DEVICE, id);
      this.onLog(`기기 선택: ${d.name || id}`);
    }
    this.deviceId = id;
    await BleClient.connect(id, () => this._onDropped(), { timeout: 10000 });
    this.asm.reset();
    await BleClient.startNotifications(id, SERVICE_UUID, CHAR_UUID, (v) => {
      this.asm.push(new Uint8Array(v.buffer, v.byteOffset, v.byteLength));
    });
    this.onLog("블루투스 연결됨");
  }

  async _connectWeb() {
    if (!this.webDevice) {
      this.webDevice = await navigator.bluetooth.requestDevice({
        filters: [{ namePrefix: "TAP-" }], optionalServices: [SERVICE_UUID],
      });
      this.webDevice.addEventListener("gattserverdisconnected", () => this._onDropped());
    }
    const server = await this.webDevice.gatt.connect();
    const ch = await (await server.getPrimaryService(SERVICE_UUID)).getCharacteristic(CHAR_UUID);
    this.rx = await (await server.getPrimaryService(SERVICE_UUID)).getCharacteristic(RX_UUID).catch(() => null);
    this.asm.reset();
    ch.addEventListener("characteristicvaluechanged", (e) => {
      const v = e.target.value;
      this.asm.push(new Uint8Array(v.buffer, v.byteOffset, v.byteLength));
    });
    await ch.startNotifications();
    this.onLog(`블루투스 연결됨: ${this.webDevice.name}`);
  }

  // 연결이 끊기면 사용자가 끊은 게 아닐 때 자동으로 다시 연결 시도
  async _onDropped() {
    if (this.userStopped || this._retrying) return;
    this._retrying = true;
    this.onState("reconnecting");
    this.onLog("연결이 끊겼어요. 다시 연결하는 중…");
    let wait = 2000;
    while (!this.userStopped) {
      await sleep(wait);
      if (this.userStopped) break;
      try {
        if (isNative()) await this._connectNative(false);
        else await this._connectWeb();
        this.onState("connected");
        break;
      } catch (e) {
        this.onLog(`재연결 실패: ${e.message || e}`);
        wait = Math.min(wait * 1.5, 10000);
      }
    }
    this._retrying = false;
  }

  async disconnect() {
    this.userStopped = true;
    try {
      if (isNative() && this.deviceId) await BleClient.disconnect(this.deviceId);
      else if (this.webDevice?.gatt?.connected) this.webDevice.gatt.disconnect();
    } catch { /* 이미 끊김 */ }
    this.onState("idle");
    this.onLog("블루투스 연결을 끊었어요");
  }
}
