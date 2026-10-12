// FFT 그래프 (새 디자인): 주황 막대 = FFT 크기, 연두 박스 = 정상 범위(Peak 주파수 × Peak 크기), 핑크 점 = 이번 Peak.
// - 이번 Peak(점)가 연두 박스 안에 들어오면 정상. 막대 모양이 박스 밖으로 나가도 괜찮음.
// - 점에 마우스를 올리거나(폰은 점을 톡 누르면) 핑크·흰색 말풍선으로 Peak 값이 보임.
// - 그래프 위를 대각선으로 끌면 그 부분이 확대됨 (더블클릭 / "확대 해제" 로 되돌림).
//   폰처럼 좁은 화면에서는 스크롤과 겹치지 않게 "확대" 버튼을 눌러 큰 창에서 확대함.
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
    const px = Math.max(fmax * 0.012, 0), py = scale ? 0.025 * scale : 0;      // 박스를 정상 범위보다 아주 조금 크게
    box = {
      x0: Math.max(band[0] - px, 0), x1: band[1] + px,
      v0: scale && magBand ? Math.max(magBand[0] * scale - py, 0) : 0,
      v1: scale && magBand ? magBand[1] * scale + py : null,
    };
    if (box.v1 != null) top = Math.max(top, box.v1);
  }
  return { n, fmax, bin, peakV, scale, box, top: Math.min(top * 1.12, 130) };
}

// 확대 상태(view)에 따라 그래프 안쪽 HTML 만들기
function inner(args, view, h) {
  const m = model(args);
  const { trace, peakHz, magBand, mag } = args;
  const v = view || { x0: 0, x1: m.fmax, v0: 0, v1: m.top };
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
  const zoomed = !!view;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((r) => `<span>${tickText(v.x0 + xs * r, xs)}</span>`).join("");
  return `<div class="spx"><div class="spp" style="height:${h}px">${box}${bars}<i class="spax"></i>${edge}${peak}` +
    `<div class="spsel" hidden></div><button type="button" class="spreset" ${zoomed ? "" : "hidden"}>확대 해제</button></div>` +
    `<div class="spticks">${ticks}</div></div>`;
}

// 카드 안에 들어갈 그래프 HTML. 인자는 기존과 같고, 마지막 extra 만 새로 추가됨.
// extra = { mag: 이번 Peak 크기, magBand: [하한, 상한] (정상 Peak 크기 범위) }
export function spectrumHtml(trace, peakHz, band, label, extra = {}) {
  const args = { trace, peakHz, band: band || null, mag: Number(extra.mag) || 0, magBand: extra.magBand || null, label };
  const data = esc(JSON.stringify(args));
  return `<div class="spw" data-sp="${data}" role="img" aria-label="${esc(label)} FFT 그래프, Peak ${esc(hzText(peakHz))}">${inner(args, null, 150)}` +
    `<button type="button" class="spbig" aria-label="${esc(label)} 그래프 크게 보기">확대</button></div>`;
}

const narrow = () => !window.matchMedia("(min-width: 680px)").matches;

// 화면에 그려진 그래프에 끌어서 확대 / 말풍선 / 크게 보기 기능을 붙임. 화면을 다시 그린 뒤마다 한 번 불러 주세요.
export function wireSpectra(root = document) {
  root.querySelectorAll(".spw").forEach((w) => {
    if (w._wired) return;
    w._wired = true;
    const args = JSON.parse(w.dataset.sp);
    const h = w.classList.contains("big") ? 320 : 150;
    let view = null;
    const draw = () => {
      const old = w.querySelector(".spx");
      const tmp = document.createElement("div");
      tmp.innerHTML = inner(args, view, h);
      old.replaceWith(tmp.firstChild);
      bind();
    };
    const bind = () => {
      const p = w.querySelector(".spp"), sel = w.querySelector(".spsel"), m = model(args);
      const cur = view || { x0: 0, x1: m.fmax, v0: 0, v1: m.top };
      let st = null;
      const frac = (e) => {
        const r = p.getBoundingClientRect();
        return { fx: clamp((e.clientX - r.left) / r.width, 0, 1), fy: clamp((e.clientY - r.top) / r.height, 0, 1) };
      };
      p.onpointerdown = (e) => {
        if (e.target.closest(".spreset") || e.target.closest(".pkw")) return;
        if (!w.classList.contains("big") && narrow()) return;          // 좁은 화면은 스크롤 우선 (확대는 큰 창에서)
        const f = frac(e);
        st = { sx: f.fx, sy: f.fy, cx: f.fx, cy: f.fy };
        try { p.setPointerCapture(e.pointerId); } catch { /* 무시 */ }
      };
      p.onpointermove = (e) => {
        if (!st) return;
        const f = frac(e);
        st.cx = f.fx; st.cy = f.fy;
        sel.hidden = false;
        sel.style.left = Math.min(st.sx, st.cx) * 100 + "%"; sel.style.top = Math.min(st.sy, st.cy) * 100 + "%";
        sel.style.width = Math.abs(st.cx - st.sx) * 100 + "%"; sel.style.height = Math.abs(st.cy - st.sy) * 100 + "%";
      };
      const end = () => {
        if (!st) return;
        const a = st; st = null; sel.hidden = true;
        const x0 = Math.min(a.sx, a.cx), x1 = Math.max(a.sx, a.cx), y0 = Math.min(a.sy, a.cy), y1 = Math.max(a.sy, a.cy);
        if (x1 - x0 < 0.03 || y1 - y0 < 0.05) return;                  // 너무 작게 끌면 무시
        const xs = cur.x1 - cur.x0, vs = cur.v1 - cur.v0;
        const nv0 = cur.v0 + (1 - y1) * vs, nv1 = cur.v0 + (1 - y0) * vs;
        if (nv1 - nv0 < 0.5) return;
        view = { x0: cur.x0 + x0 * xs, x1: cur.x0 + x1 * xs, v0: Math.max(0, nv0), v1: nv1 };
        draw();
      };
      p.onpointerup = end; p.onpointercancel = end;
      p.ondblclick = () => { if (view) { view = null; draw(); } };
      const rs = w.querySelector(".spreset");
      if (rs) rs.onclick = () => { view = null; draw(); };
    };
    bind();
    const big = w.querySelector(".spbig");
    if (big) big.onclick = () => openSheet(args);
  });
}

// 폰: 큰 창을 띄워 그 안에서 끌어서 확대
function openSheet(args) {
  const sheet = document.createElement("div");
  sheet.className = "spsheet";
  sheet.innerHTML = `<div class="spsheet-in"><div class="spsheet-h"><div><strong>${esc(args.label)}</strong><small>끌어서 사각형으로 감싼 부분이 확대돼요</small></div>` +
    `<button type="button" class="spclose" aria-label="닫기">✕</button></div>` +
    `<div class="spw big" data-sp="${esc(JSON.stringify(args))}">${inner(args, null, 320)}</div></div>`;
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.remove(); });
  sheet.querySelector(".spclose").onclick = () => sheet.remove();
  document.body.appendChild(sheet);
  wireSpectra(sheet);
}
