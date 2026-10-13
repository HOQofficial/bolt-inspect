// FFT 그래프 (새 디자인): 주황 막대 = FFT 크기, 연두 박스 = 정상 범위(Peak 주파수 × Peak 크기), 핑크 점 = 이번 Peak.
// - 이번 Peak(점)가 연두 박스 안에 들어오면 정상. 막대 모양이 박스 밖으로 나가도 괜찮음.
// - 점에 마우스를 올리거나(폰은 점을 톡 누르면) 핑크·흰색 말풍선으로 Peak 값이 보임.
// - 처음에는 전체(0~f_max)를 보여 주고, 연두 박스(정상 Peak 크기 범위)는 가로로 그래프 끝에서 끝까지 길게 뻗음.
// - 폰·태블릿: 두 손가락으로 벌리면 확대, 오므리면 축소, 확대한 상태에서 한 손가락을 좌우로 끌면 이동. 더블탭 / "원래대로" 로 되돌림.
// - PC(마우스): 그래프 위를 끌면 사각형으로 확대, 더블클릭 / "원래대로" 로 되돌림.
// ESP32 가 보낸 막대(0~100)를 그대로 그림. 막대의 주파수 범위는 f_max(Hz) 까지. 판정 계산에는 관여하지 않음(그리기 전용).
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const hzText = (f) => (f >= 1000 ? `${Number((f / 1000).toFixed(2))} kHz` : `${Math.round(f)} Hz`);
const tickText = (f, span) => (span >= 2000 ? (f === 0 ? "0" : `${Number((f / 1000).toFixed(1))}k`) : span >= 20 ? String(Math.round(f)) : f.toFixed(1));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// 그림에 필요한 값 계산 (그리기 전용, 판정과 무관)
// args = { trace:{f_max,v[]}, peakHz, band:[lo,hi]|null, mag, magBand:[lo,hi]|null, label }
function model(args) {
  const { trace, peakHz, band, mag, magBand } = args;
  const n = trace.v.length, fmax = trace.f_max;
  const bin = clamp(Math.floor((peakHz / fmax) * n), 0, n - 1);
  const peakV = Math.max(trace.v[bin - 1] ?? 0, trace.v[bin], trace.v[bin + 1] ?? 0);   // Peak 위치의 막대 높이
  // 막대 높이(0~100)와 'Peak 크기' 숫자를 이어 주는 비율. Peak 위치 막대 = 이번 Peak 크기라고 보고 계산.
  const scale = mag > 0 && peakV > 0 ? peakV / mag : null;
  const maxV = Math.max(...trace.v, 1);
  let top = maxV;
  let box = null;
  if (band && band[1] > 0) {
    const py = scale ? 0.025 * scale : 0;      // 박스를 정상 범위보다 아주 조금 높게
    box = {
      x0: 0, x1: fmax,                          // 가로로 그래프 끝에서 끝까지 길게 (세로 = 정상 Peak 크기 범위)
      v0: scale && magBand ? Math.max(magBand[0] * scale - py, 0) : 0,
      v1: scale && magBand ? magBand[1] * scale + py : null,
    };
    if (box.v1 != null) top = Math.max(top, box.v1);
  }
  return { n, fmax, peakHz, bin, peakV, scale, box, top: Math.min(top * 1.12, 130) };
}

// 보이는 범위(view) = { x0, x1, v0, v1 } (주파수, 막대 높이)
const fullView = (m) => ({ x0: 0, x1: m.fmax, v0: 0, v1: m.top });
// 처음 보여 줄 범위 = 전체 (0 ~ f_max). 연두 박스는 가로로 길게 뻗어 있음.
const defView = (m) => fullView(m);
function clampView(v, m) {
  const full = fullView(m);
  let xs = clamp(v.x1 - v.x0, m.fmax * 0.02, full.x1), vs = clamp(v.v1 - v.v0, full.v1 * 0.04, full.v1);
  const x0 = clamp(v.x0, 0, full.x1 - xs), v0 = clamp(v.v0, 0, full.v1 - vs);
  return { x0, x1: x0 + xs, v0, v1: v0 + vs };
}
const sameView = (a, b) => ["x0", "x1", "v0", "v1"].every((k) => Math.abs(a[k] - b[k]) < 1e-6);

// 그래프 안쪽(막대·박스·Peak 점)만 HTML 로 만들기 — 움직이는 중에도 이 부분만 다시 그림
function layer(args, view) {
  const m = model(args);
  const { trace, peakHz, magBand, mag } = args;
  const v = view;
  const xs = v.x1 - v.x0, vs = v.v1 - v.v0;
  const X = (f) => ((f - v.x0) / xs) * 100;
  const Y = (val) => 100 - ((val - v.v0) / vs) * 100;
  const bw = (m.fmax / m.n / xs) * 100;
  let bars = "";
  trace.v.forEach((val, i) => {
    const f0 = (i / m.n) * m.fmax, f1 = ((i + 1) / m.n) * m.fmax;
    if (f1 < v.x0 || f0 > v.x1 || val <= v.v0) return;
    const l0 = clamp(X(f0) + bw * 0.14, 0, 100), r0 = clamp(X(f0) + bw * 0.86, 0, 100);
    if (r0 - l0 <= 0.05) return;
    bars += `<i class="spb" style="left:${l0.toFixed(2)}%;width:${(r0 - l0).toFixed(2)}%;height:${clamp(((val - v.v0) / vs) * 100, 0, 104).toFixed(2)}%"></i>`;
  });
  let box = "", edge = "";
  if (m.box) {
    const t = m.box.v1 == null ? 0 : clamp(Y(m.box.v1), 0, 100), b = clamp(Y(m.box.v0), 0, 100);
    const l = clamp(X(m.box.x0), 0, 100), r = clamp(X(m.box.x1), 0, 100);
    if (r > l && b > t) box = `<div class="spbox" style="left:${l.toFixed(2)}%;width:${(r - l).toFixed(2)}%;top:${t.toFixed(2)}%;height:${(b - t).toFixed(2)}%"></div>`;
    if (m.scale && magBand) {
      for (const [num, val] of [[magBand[1], m.box.v1], [magBand[0], m.box.v0]]) {
        const yy = Y(val);
        if (yy > 3 && yy < 97) edge += `<span class="spe" style="top:${yy.toFixed(2)}%">${num.toFixed(2)}</span>`;
      }
    }
  }
  const px = X(peakHz), py = Y(m.peakV);
  const vis = px >= 1 && px <= 99 && py >= 2 && py <= 98;
  const right = px > 55;
  const peak = `<div class="pkw" tabindex="0" style="left:${px.toFixed(2)}%;top:${py.toFixed(2)}%;opacity:${vis ? 1 : 0};pointer-events:${vis ? "auto" : "none"}">` +
    `<i class="pkh"></i><i class="pkd"></i>` +
    `<div class="pkt" style="${right ? "right:16px" : "left:16px"}"><b>PEAK 크기</b><strong>${Number(mag).toFixed(2)}</strong><em>${esc(hzText(peakHz))}</em></div></div>`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((r) => `<span>${tickText(v.x0 + xs * r, xs)}</span>`).join("");
  return { html: `${box}${bars}<i class="spax"></i>${edge}${peak}`, ticks };
}

// 카드 안에 들어갈 그래프 HTML. 인자는 기존과 같고, 마지막 extra 만 새로 추가됨.
// extra = { mag: 이번 Peak 크기, magBand: [하한, 상한] (정상 Peak 크기 범위) }
export function spectrumHtml(trace, peakHz, band, label, extra = {}) {
  const args = { trace, peakHz, band: band || null, mag: Number(extra.mag) || 0, magBand: extra.magBand || null, label };
  const m = model(args);
  const L = layer(args, defView(m));
  return `<div class="spw" data-sp="${esc(JSON.stringify(args))}" role="img" aria-label="${esc(label)} FFT 그래프, Peak ${esc(hzText(peakHz))}">` +
    `<div class="spx"><div class="spp" style="height:150px"><div class="spl">${L.html}</div>` +
    `<div class="spsel" hidden></div><button type="button" class="spreset" hidden>원래대로</button></div>` +
    `<div class="spticks">${L.ticks}</div></div></div>`;
}

// 화면에 그려진 그래프에 확대·이동·말풍선 기능을 붙임. 화면을 다시 그린 뒤마다 한 번 불러 주세요.
export function wireSpectra(root = document) {
  root.querySelectorAll(".spw").forEach((w) => {
    if (w._wired) return;
    w._wired = true;
    const args = JSON.parse(w.dataset.sp);
    const m = model(args), full = fullView(m), def = defView(m);
    const p = w.querySelector(".spp"), sel = w.querySelector(".spsel"), lay = w.querySelector(".spl"), tk = w.querySelector(".spticks"), rs = w.querySelector(".spreset");
    let view = def;
    const draw = () => {
      const L = layer(args, view);
      lay.innerHTML = L.html; tk.innerHTML = L.ticks;
      rs.hidden = sameView(view, def);
    };
    const ptrs = new Map();            // 화면에 닿아 있는 손가락(또는 마우스)
    let g = null;                      // 지금 하는 동작: 사각형 확대(마우스) / 이동(손가락 1개) / 두 손가락 확대·축소
    const rect = () => p.getBoundingClientRect();
    const frac = (e) => { const r = rect(); return { fx: clamp((e.clientX - r.left) / r.width, 0, 1), fy: clamp((e.clientY - r.top) / r.height, 0, 1) }; };
    const startTouchGesture = () => {
      const pts = [...ptrs.values()], r = rect();
      if (pts.length >= 2) {
        const [a, b] = pts, d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
        const mx = ((a.x + b.x) / 2 - r.left) / r.width, my = ((a.y + b.y) / 2 - r.top) / r.height;
        g = { kind: "pinch", d0: d, v0: { ...view }, mx0: mx, my0: my };
        g.fx = view.x0 + mx * (view.x1 - view.x0); g.fy = view.v1 - my * (view.v1 - view.v0);   // 두 손가락 가운데 아래의 실제 값(주파수·높이)
      } else if (pts.length === 1) {
        g = { kind: "pan", x: pts[0].x, v0: { ...view } };
      } else g = null;
    };
    p.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".spreset") || e.target.closest(".pkw")) return;
      if (e.pointerType === "mouse") {
        if (e.button !== 0) return;
        const f = frac(e);
        g = { kind: "rect", sx: f.fx, sy: f.fy, cx: f.fx, cy: f.fy };
      } else {
        ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
        startTouchGesture();
      }
      try { p.setPointerCapture(e.pointerId); } catch { /* 무시 */ }
    });
    p.addEventListener("pointermove", (e) => {
      if (!g) return;
      if (g.kind === "rect") {
        const f = frac(e);
        g.cx = f.fx; g.cy = f.fy; sel.hidden = false;
        sel.style.left = Math.min(g.sx, g.cx) * 100 + "%"; sel.style.top = Math.min(g.sy, g.cy) * 100 + "%";
        sel.style.width = Math.abs(g.cx - g.sx) * 100 + "%"; sel.style.height = Math.abs(g.cy - g.sy) * 100 + "%";
        return;
      }
      if (!ptrs.has(e.pointerId)) return;
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
      const r = rect(), pts = [...ptrs.values()];
      if (g.kind === "pinch" && pts.length >= 2) {
        const [a, b] = pts, d = Math.hypot(a.x - b.x, a.y - b.y) || 1, s = g.d0 / d;        // 벌리면 s<1 → 더 좁은 범위(확대)
        const xs = (g.v0.x1 - g.v0.x0) * s, vs = (g.v0.v1 - g.v0.v0) * s;
        const mx = ((a.x + b.x) / 2 - r.left) / r.width, my = ((a.y + b.y) / 2 - r.top) / r.height;
        view = clampView({ x0: g.fx - mx * xs, x1: g.fx - mx * xs + xs, v1: g.fy + my * vs, v0: g.fy + my * vs - vs }, m);
        draw();
      } else if (g.kind === "pan" && pts.length === 1) {
        const dx = (pts[0].x - g.x) / r.width * (g.v0.x1 - g.v0.x0);                             // 손가락을 따라 좌우로 이동
        view = clampView({ ...g.v0, x0: g.v0.x0 - dx, x1: g.v0.x1 - dx }, m);
        draw();
      }
    });
    const end = (e) => {
      if (g && g.kind === "rect") {
        const a = g; g = null; sel.hidden = true;
        const x0 = Math.min(a.sx, a.cx), x1 = Math.max(a.sx, a.cx), y0 = Math.min(a.sy, a.cy), y1 = Math.max(a.sy, a.cy);
        if (x1 - x0 < 0.03 || y1 - y0 < 0.05) return;                  // 너무 작게 끌면 무시
        const xs = view.x1 - view.x0, vs = view.v1 - view.v0;
        view = clampView({ x0: view.x0 + x0 * xs, x1: view.x0 + x1 * xs, v0: view.v0 + (1 - y1) * vs, v1: view.v0 + (1 - y0) * vs }, m);
        draw();
        return;
      }
      ptrs.delete(e.pointerId);
      startTouchGesture();             // 남은 손가락으로 동작을 이어 감 (두 손가락 → 한 손가락)
    };
    p.addEventListener("pointerup", end);
    p.addEventListener("pointercancel", end);
    const reset = () => { view = def; draw(); };
    p.addEventListener("dblclick", reset);
    rs.onclick = reset;
  });
}
