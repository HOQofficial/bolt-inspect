// PC 대시보드(dashboard/ui.py 의 gauge)와 같은 막대 게이지: 초록 = 정상 범위, 파란 막대 = 측정값, 검은 선 = 측정값 위치.
// 폰 화면은 한 줄에 라벨·값, 아래에 막대, 맨 아래에 정상 범위 글자 (gaugeCompactHtml).
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ui.py gauge() 와 같은 계산: 축 범위와 색 칸
export function gaugeRange(val, lo, hi, unit = "") {
  const span = Math.max(hi - lo, 1e-9), pad = 0.65 * span;
  let xmin = lo - pad, xmax = hi + pad;
  const margin = 0.1 * Math.max(xmax - xmin, 1e-9);
  xmin = Math.min(xmin, val - margin);          // 측정값이 범위 밖이어도 축 안에 보이게
  xmax = Math.max(xmax, val + margin);
  xmin = Math.max(0, xmin);                     // 특징값은 모두 0 이상
  if (unit.trim() === "%") xmax = Math.min(xmax, 100);
  return { xmin, xmax, loC: Math.max(lo, xmin), hiC: Math.min(hi, xmax) };
}

export function niceTicks(a, b, n = 5) {
  const raw = (b - a) / (n - 1), pow = 10 ** Math.floor(Math.log10(raw)), f = raw / pow;
  const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * pow;
  const out = [];
  for (let t = Math.ceil(a / step) * step; t <= b + step * 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}
const tickText = (t) => (Math.abs(t) >= 1000 ? `${Number((t / 1000).toFixed(2))}k` : String(Number(t.toFixed(3))));

// 한 줄짜리 게이지 HTML. label 예: "Peak Frequency (Hz)", valueText 예: "3200 Hz"
export function gaugeHtml(label, val, lo, hi, unit, valueText) {
  const { xmin, xmax, loC, hiC } = gaugeRange(val, lo, hi, unit);
  const inside = lo <= val && val <= hi;
  const cls = inside ? "in" : "out";
  const p = (v) => ((v - xmin) / (xmax - xmin)) * 100;
  const rects = [[xmin, loC, "var(--gauge-bg)"], [loC, hiC, "var(--gauge-ok)"], [hiC, xmax, "var(--gauge-bg)"]]
    .filter(([a, b]) => b > a)
    .map(([a, b, c]) => `<rect x="${p(a).toFixed(3)}" y="0" width="${(p(b) - p(a)).toFixed(3)}" height="10" fill="${c}"/>`).join("");
  const pv = Math.min(100, Math.max(0, p(val)));
  const bar = `<rect x="0" y="3.2" width="${pv.toFixed(3)}" height="3.6" fill="var(--gauge-bar)"/>`;
  const thr = `<line x1="${pv.toFixed(3)}" x2="${pv.toFixed(3)}" y1="0" y2="10" stroke="var(--gauge-thr)" stroke-width="3" vector-effect="non-scaling-stroke"/>`;
  const ticks = niceTicks(xmin, xmax).map((t) => `<span style="left:${p(t).toFixed(2)}%">${tickText(t)}</span>`).join("");
  return `<div class="g"><div class="gl ${cls}">${inside ? "✓" : "✕"} ${esc(label)}</div>` +
    `<div class="gb"><svg viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="${esc(label)} ${esc(valueText)}">${rects}${bar}${thr}</svg>` +
    `<div class="gt">${ticks}</div></div><div class="gv ${cls}">${esc(valueText)}</div></div>`;
}

// 폰용 간결한 게이지: 라벨 + 값 한 줄, 둥근 막대(정상 범위 = 연한 칸, 측정값 = 동그란 점), 정상 범위 글자.
// 예) rangeText = "정상 280 ~ 340 Hz"
export function gaugeCompactHtml(label, val, lo, hi, unit, valueText, rangeText) {
  const { xmin, xmax, loC, hiC } = gaugeRange(val, lo, hi, unit);
  const inside = lo <= val && val <= hi;
  const cls = inside ? "in" : "out";
  const p = (v) => Math.min(100, Math.max(0, ((v - xmin) / (xmax - xmin)) * 100));
  return `<div class="gc ${cls}"><div class="gc-top"><span class="gc-l">${esc(label)}</span><span class="gc-v">${esc(valueText)}</span></div>` +
    `<div class="gtrack" role="img" aria-label="${esc(label)} ${esc(valueText)}">` +
    `<i class="gband" style="left:${p(loC).toFixed(2)}%;width:${(p(hiC) - p(loC)).toFixed(2)}%"></i>` +
    `<i class="gdot" style="left:${p(val).toFixed(2)}%"></i></div>` +
    `<div class="gc-r">${inside ? "정상 범위 안" : "정상 범위 밖"} · ${esc(rangeText)}</div></div>`;
}
