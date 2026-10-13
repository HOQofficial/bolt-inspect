/* FFT 펼침 카드 그리기 (검사 기록 표와 플랜지 카드의 점이 같이 씀). window.RSFFT.panel(d) 가 HTML 글자를 돌려줌 */
(function () {
  if (window.RSFFT) return;
  var KO = { OK: "정상", CHECK: "재측정 필요", NG: "체결 이상 의심" };
  var COL = { OK: ["#d9f2e4", "#14633f"], CHECK: ["#ffebc2", "#7a5200"], NG: ["#ffd9d6", "#8e2019"] };
  var NAME = { mic: "음향", acc: "진동" }, TAG = { mic: "INMP441 · FFT", acc: "MPU6050 · FFT" };
  var LBL = { peak_hz: "Peak 주파수", mag: "Peak 크기", energy_pct: "대역 에너지" };
  var BAR = { mic: "#ff6a1f", acc: "#3347ff" };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function fmt(s, k, v) {
    if (k === "peak_hz") return Math.round(v).toLocaleString("en-US") + " Hz";
    if (k === "mag") return v.toFixed(3) + (s === "acc" ? " g" : "");
    return v.toFixed(1) + " %";
  }
  function hzText(f) { return f >= 1000 ? (Math.round(f / 10) / 100) + " kHz" : Math.round(f) + " Hz"; }

  // 정상 범위(초록 칸) 안에 이번 값(주황 점)이 있는지 보여주는 막대
  function sliders(s, feats, rr) {
    var out = "";
    ["peak_hz", "mag", "energy_pct"].forEach(function (k) {
      var v = feats[k], lo = v, hi = v, ok = true;
      if (rr && rr[k]) { lo = rr[k][0]; hi = rr[k][1]; ok = v >= lo && v <= hi; }
      var span = Math.max(hi - lo, 1e-9), a0 = lo - 0.65 * span, a1 = hi + 0.65 * span;
      a0 = Math.max(Math.min(a0, v - 0.1 * span), 0); a1 = Math.max(a1, v + 0.1 * span);
      if (k === "energy_pct") a1 = Math.min(a1, 100);
      var w = Math.max(a1 - a0, 1e-9);
      var pos = function (x) { return 100 * clamp((x - a0) / w, 0, 1); };
      out += '<div class="rs-sl"><div class="rs-slt"><span>' + LBL[k] + '</span><b style="color:' + (ok ? "#0b0f1e" : "#c0302a") + '">' + fmt(s, k, v) + "</b></div>" +
        '<div class="rs-slb">' + (rr && rr[k] ? '<i class="rng" style="left:' + pos(lo).toFixed(1) + "%;width:" + (pos(hi) - pos(lo)).toFixed(1) + '%"></i>' : "") +
        '<i class="dot" style="left:' + pos(v).toFixed(1) + '%"></i></div></div>';
    });
    return '<div class="rs-slw">' + out + "</div>";
  }

  // FFT 막대 그래프: 주황/파랑 막대 = FFT 크기, 연두 박스 = 정상 범위(Peak 주파수 × Peak 크기), 핑크 점 = 이번 Peak
  function chart(s, tr, feats, rr) {
    var v = tr.v, n = v.length, fmax = tr.f_max;
    var bin = clamp(Math.floor(feats.peak_hz / fmax * n), 0, n - 1);
    var peakV = Math.max(v[bin - 1] || 0, v[bin], v[bin + 1] || 0);
    var scale = feats.mag > 0 && peakV > 0 ? peakV / feats.mag : null;
    var top = Math.max.apply(null, v.concat([1]));
    var box = "";
    var bounds = null;
    if (rr && rr.peak_hz && rr.peak_hz[1] > 0) {
      var px = fmax * 0.012, py = scale ? 0.025 * scale : 0;
      var y0 = 0, y1 = null;
      if (scale && rr.mag) { y0 = Math.max(rr.mag[0] * scale - py, 0); y1 = rr.mag[1] * scale + py; top = Math.max(top, y1); }
      bounds = { x0: Math.max(rr.peak_hz[0] - px, 0), x1: rr.peak_hz[1] + px, y0: y0, y1: y1 };
    }
    var T = Math.min(top * 1.12, 130);
    var bars = "";
    for (var i = 0; i < n; i++) {
      var l = (i / n) * 100, w = 100 / n;
      bars += '<i class="hxb" style="left:' + (l + w * 0.14).toFixed(2) + "%;width:" + (w * 0.72).toFixed(2) + "%;height:" + clamp(v[i] / T * 100, 0, 100).toFixed(2) + "%;background:" + BAR[s] + '"></i>';
    }
    if (bounds) {
      var t = bounds.y1 == null ? 0 : 100 - clamp(bounds.y1 / T * 100, 0, 100), b = 100 - clamp(bounds.y0 / T * 100, 0, 100);
      var l0 = clamp(bounds.x0 / fmax * 100, 0, 100), r0 = clamp(bounds.x1 / fmax * 100, 0, 100);
      if (r0 > l0 && b > t) box = '<div class="hxbox" style="left:' + l0.toFixed(2) + "%;width:" + (r0 - l0).toFixed(2) + "%;top:" + t.toFixed(2) + "%;height:" + (b - t).toFixed(2) + '%"></div>';
    }
    var pxp = clamp(feats.peak_hz / fmax * 100, 0, 100), pyp = 100 - clamp(peakV / T * 100, 0, 100);
    var dot = '<i class="hxd" style="left:' + pxp.toFixed(2) + "%;top:" + pyp.toFixed(2) + '%" title="PEAK 크기 ' + feats.mag.toFixed(2) + " · " + hzText(feats.peak_hz) + '"></i>';
    var step = [50, 100, 200, 250, 500, 1000, 2000, 2500].filter(function (c) { return fmax / c <= 5; })[0] || fmax;
    var ticks = "";
    for (var f = 0; f < fmax; f += step) ticks += '<span style="left:' + (f / fmax * 100) + '%">' + f + " Hz</span>";
    return '<div class="hxc">' + box + bars + dot + '</div><div class="hxt">' + ticks + "</div>";
  }

  function panel(d) {
    var ps = ["mic", "acc"].map(function (s) {
      var feats = d.f && d.f[s], rr = d.ref && d.ref[s];
      var h = '<div class="hxcard"><div class="rs-evh"><b>' + NAME[s] + "</b><span>" + TAG[s] + "</span></div>";
      if (!feats) return h + '<p class="hxn">이번 측정에 ' + NAME[s] + " 값이 오지 않았어요.</p></div>";
      var tr = d.sp && d.sp[s];
      h += tr ? chart(s, tr, feats, rr) : '<p class="hxn">이 측정에는 FFT 그래프 데이터가 없어요 (예전 펌웨어/앱으로 측정한 기록).</p>';
      if (!rr) h += '<p class="hxn">정상 기준이 없어 범위 비교는 하지 않았어요.</p>';
      return h + sliders(s, feats, rr) + "</div>";
    }).join("");
    var c = COL[d.r] || ["#eceef7", "#3a4056"];
    return '<div class="rs-hd"><div class="hxh"><b>' + esc(d.n) + "</b><span>" + esc(d.t) + ' 측정</span><em style="background:' + c[0] + ";color:" + c[1] + '">' + (KO[d.r] || "") + "</em>" +
      (d.src ? "<small>" + esc(d.src) + "</small>" : "") + '</div><div class="hxg">' + ps + "</div>" +
      '<p class="hxf">연두 박스 = 정상 범위(Peak 주파수 × Peak 크기), 핑크 점 = 이번 Peak · 아래 막대의 연두 칸 = 정상 범위(지금 등록된 기준), 주황 점 = 이번 값</p></div>';
  }

  window.RSFFT = { panel: panel };
})();
