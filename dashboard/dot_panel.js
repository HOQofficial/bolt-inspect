/* 플랜지 카드의 볼트 점(원)을 누르면 아래에 그 볼트의 가장 최근 타음 측정 FFT 가 열리고, 같은 점을 다시 누르면 닫힘 */
(function () {
  var W = window;
  function hostOf(c) { return c && document.getElementById("rs-dotpanel-" + (c.getAttribute("data-r") || 0)); }
  function clearAll() { document.querySelectorAll('[id^="rs-dotpanel-"]').forEach(function (h) { h.innerHTML = ""; }); }
  function dotOf(k) { return document.querySelector('.rs-fl circle[data-k="' + k + '"]'); }
  function mark(k) {
    document.querySelectorAll(".rs-fl circle.sel").forEach(function (c) { c.classList.remove("sel"); });
    var c = k && dotOf(k);
    if (c) c.classList.add("sel");
  }
  function show(c, scroll) {
    var h = hostOf(c), d;
    if (!h) return;
    clearAll();                                          // 다른 줄에 열려 있던 것은 닫음
    try { d = JSON.parse(c.getAttribute("data-d")); } catch (e) { return; }
    h.innerHTML = '<div class="rs-dp">' + W.RSFFT.panel(d) + "</div>";
    W.__dotOpen = c.getAttribute("data-k");
    mark(W.__dotOpen);
    if (scroll && h.scrollIntoView) h.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function hide() {
    clearAll();
    W.__dotOpen = null;
    mark(null);
  }
  if (!W.__dotBound) {                                   // 한 번만 붙임 (화면이 다시 그려져도 계속 동작)
    W.__dotBound = true;
    document.addEventListener("click", function (e) {
      var c = e.target && e.target.closest && e.target.closest(".rs-fl circle[data-d]");
      if (!c) return;
      if (W.__dotOpen === c.getAttribute("data-k")) hide(); else show(c, true);
    });
  }
  // 자동 새로고침으로 화면이 다시 그려져도 열어 둔 점의 FFT 를 유지
  (function wait(n) {
    var k = W.__dotOpen, c = k && dotOf(k), h = hostOf(c);
    if (!k) return;
    if (h) { if (!h.firstChild) show(c, false); }
    else if (n < 40) setTimeout(function () { wait(n + 1); }, 50);
    else W.__dotOpen = null;                             // 그 점이 더 이상 화면에 없음 (보기 조건이 바뀜)
  })(0);
})();
