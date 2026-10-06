// BLE 로 20바이트씩 조각나서 오는 글자를 줄바꿈(\n)까지 이어 붙여 한 줄씩 돌려줌.
export class LineAssembler {
  constructor(onLine) {
    this.onLine = onLine;
    this.buf = "";
    this.dec = new TextDecoder("utf-8");
  }
  push(bytes) {                       // bytes: Uint8Array
    this.buf += this.dec.decode(bytes, { stream: true });
    let i;
    while ((i = this.buf.indexOf("\n")) >= 0) {
      const line = this.buf.slice(0, i).trim();
      this.buf = this.buf.slice(i + 1);
      if (line) this.onLine(line);
    }
    if (this.buf.length > 600) this.buf = "";   // 줄바꿈이 영영 안 오면 버퍼가 커지지 않게 버림
  }
  reset() { this.buf = ""; }
}
