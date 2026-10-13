/* 전체 검사 기록 표: 행을 누르면 바로 아래에 그때 측정한 FFT 가 열리고, 다시 누르면 닫힘.
   그리기 전용 (판정과 무관). 데이터는 각 행의 data-d 에 들어 있음. 화면이 새로 그려져도(자동 새로고침) 열어 둔 행과 스크롤 위치를 유지함. */
(function () {
  var ID = "__ID__";                      // 표 이름 (표가 둘 이상이어도 서로 따로 움직이게)
  var tries = 0;
  // st.html 은 스크립트를 표보다 먼저 실행할 수 있어서, 표가 화면에 나타날 때까지 잠깐씩 기다렸다가 붙임
  (function wait() {
    var r = document.getElementById(ID);
    if (r) { if (!r.getAttribute("data-ready")) start(r); return; }
    if (++tries < 200) setTimeout(wait, 50);
  })();
  function start(root) {
  root.setAttribute("data-ready", "1");
  var W = window;
  var panel = window.RSFFT.panel;
  var baseMax = root.style.maxHeight;                      // 평소 표 높이. 행을 열면 FFT 가 다 보이게 잠깐 더 키움
  function closeAll() {
    root.style.maxHeight = baseMax;
    root.querySelectorAll(".rs-hd").forEach(function (e) { e.remove(); });
    root.querySelectorAll(".rs-tr.open").forEach(function (e) { e.classList.remove("open"); e.setAttribute("aria-expanded", "false"); });
  }
  function open(row, scroll) {
    var d;
    try { d = JSON.parse(row.getAttribute("data-d")); } catch (e) { return; }
    closeAll();
    if (baseMax) root.style.maxHeight = "860px";
    row.classList.add("open"); row.setAttribute("aria-expanded", "true");
    row.insertAdjacentHTML("afterend", panel(d));
    W["__open_" + ID] = row.getAttribute("data-id");
    if (scroll) { var p = row.nextElementSibling; if (p && p.scrollIntoView) p.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
  }
  function toggle(row) {
    if (row.classList.contains("open")) { closeAll(); W["__open_" + ID] = null; } else open(row, true);
  }
  root.addEventListener("click", function (e) {
    var row = e.target.closest(".rs-tr[data-d]");
    if (row && root.contains(row)) toggle(row);
  });
  root.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var row = e.target.closest && e.target.closest(".rs-tr[data-d]");
    if (row) { e.preventDefault(); toggle(row); }
  });
  root.addEventListener("scroll", function () { W["__scroll_" + ID] = root.scrollTop; });
  // 자동 새로고침으로 표가 다시 그려져도 열어 둔 행과 스크롤 위치를 되살림
  if (W["__open_" + ID]) {
    var again = root.querySelector('.rs-tr[data-id="' + W["__open_" + ID] + '"]');
    if (again) open(again, false);
  }
  if (W["__scroll_" + ID]) root.scrollTop = W["__scroll_" + ID];
  }
})();
