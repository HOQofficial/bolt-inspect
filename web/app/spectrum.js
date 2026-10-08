// FFT 그래프 (PC 대시보드의 FFT 그래프와 같은 모양): 주황 선 = FFT 크기, 연한 칸 = 정상 Peak 주파수 범위, 세로선 = 이번 Peak.
// ESP32 가 보낸 막대(0~99)를 그대로 그림. 막대의 주파수 범위는 f_max(Hz) 까지.
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const hzText = (f) => (f >= 1000 ? `${Number((f / 1000).toFixed(2))} kHz` : `${Math.round(f)} Hz`);
const tickText = (f, fmax) => (fmax >= 2000 ? (f === 0 ? "0" : `${Number((f / 1000).toFixed(1))}k`) : String(Math.round(f)));

// trace = { f_max, v:[...] },  peakHz = 이번 Peak,  band = [하한, 상한] | null (정상 Peak 범위)
export function spectrumHtml(trace, peakHz, band, label) {
  const W = 320, H = 132, pl = 8, pr = 8, pt = 20, pb = 22;
  const pw = W - pl - pr, ph = H - pt - pb, n = trace.v.length, fmax = trace.f_max;
  const X = (f) => pl + (Math.min(Math.max(f, 0), fmax) / fmax) * pw;
  const Y = (v) => pt + ph * (1 - Math.min(Math.max(v, 0), 100) / 100);
  const pts = trace.v.map((v, i) => [pl + ((i + 0.5) / n) * pw, Y(v)]);
  const line = "M" + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const area = `${line} L${pts[n - 1][0].toFixed(1)},${(pt + ph).toFixed(1)} L${pts[0][0].toFixed(1)},${(pt + ph).toFixed(1)} Z`;
  let bandSvg = "";
  if (band && band[1] > 0) {
    const x1 = X(band[0]), x2 = Math.max(X(band[1]), x1 + 2);
    bandSvg = `<rect x="${x1.toFixed(1)}" y="${pt}" width="${(x2 - x1).toFixed(1)}" height="${ph}" fill="var(--gauge-ok)" rx="3"/>`;
  }
  const px = X(peakHz);
  const anchor = px > W * 0.7 ? "end" : "start";
  const tx = anchor === "end" ? px - 4 : px + 4;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((r) => {
    const f = fmax * r;
    return `<text x="${X(f).toFixed(1)}" y="${H - 6}" text-anchor="${r === 0 ? "start" : r === 1 ? "end" : "middle"}" class="sp-t">${tickText(f, fmax)}</text>`;
  }).join("");
  return `<svg class="sp" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} FFT 그래프, Peak ${esc(hzText(peakHz))}">` +
    bandSvg +
    `<line x1="${pl}" x2="${W - pr}" y1="${pt + ph}" y2="${pt + ph}" class="sp-ax"/>` +
    `<path d="${area}" class="sp-area"/><path d="${line}" class="sp-line"/>` +
    `<line x1="${px.toFixed(1)}" x2="${px.toFixed(1)}" y1="${pt - 2}" y2="${pt + ph}" class="sp-peak"/><circle cx="${px.toFixed(1)}" cy="${pt - 2}" r="3" class="sp-dot"/>` +
    `<text x="${tx.toFixed(1)}" y="${pt - 8}" text-anchor="${anchor}" class="sp-pt">Peak ${esc(hzText(peakHz))}</text>` +
    ticks + `</svg>`;
}
