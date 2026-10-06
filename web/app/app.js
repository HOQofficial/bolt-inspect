// 볼트 타음 검사 앱 화면. 블루투스로 받은 특징값 -> 정상 기준과 비교해 판정 -> 저장.
import { Capacitor } from "@capacitor/core";
import { featuresFromBle } from "../schema.js";
import { TapLink, bleSupported, hasSavedDevice, forgetDevice, isNative } from "./ble.js";
import { tappingFromFeatures, refSourceText, makeRecord, RESULT_KO } from "./judge.js";
import { validateInspection } from "./validate.js";
import { gaugeHtml } from "./gauge.js";
import { initStore, hasServer, loadFlanges, saveInspection, getHist, onHistChange, pendingCount } from "./store.js";

const $ = (id) => document.getElementById(id);
const store = (() => {                       // 설정값 기억 (검사자 이름 등). 막혀 있어도 앱은 동작
  const g = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
  const s = (k, v) => { try { localStorage.setItem(k, v); } catch { /* 무시 */ } };
  return { g, s };
})();

let flanges = [];
let current = null;          // 가장 최근 타격 { features, tapping, flange, bolt, isSim, saved, msg }
let link = null;
let hitCount = 0;

// ---------- 화면 도우미 ----------
function log(m) {
  const t = new Date().toLocaleTimeString("ko-KR", { hour12: false });
  $("log").textContent = `${t}  ${m}\n` + $("log").textContent.slice(0, 4000);
}
function notice(text) { $("notice").textContent = text || ""; $("notice").hidden = !text; }
const UNIT = { mic: { peak_hz: "Hz", mag: "0~1", energy_pct: "%" }, acc: { peak_hz: "Hz", mag: "g", energy_pct: "%" } };
const NAME = { mic: "음향", acc: "진동" };
const TITLE = { mic: "🎤 음향 · INMP441", acc: "📳 진동 · MPU6050" };
const LABEL = { peak_hz: "Peak Frequency", mag: "Peak Magnitude", energy_pct: "Band Energy" };
const ICON = { OK: "●", CHECK: "▲", NG: "■" };
const KEYS = ["peak_hz", "mag", "energy_pct"];
const fmt = (k, v) => (k === "peak_hz" ? v.toFixed(0) : k === "mag" ? v.toFixed(3) : v.toFixed(1));
const label = (s, k) => `${LABEL[k]} (${UNIT[s][k]})`;
// 게이지 옆에 쓰는 값 글자 (대시보드와 같음: Hz / 크기 / %, 진동 크기만 g)
const valText = (s, k, v) => (k === "peak_hz" ? `${fmt(k, v)} Hz` : k === "mag" ? (s === "acc" ? `${fmt(k, v)} g` : fmt(k, v)) : `${fmt(k, v)} %`);
const gUnit = (s, k) => (k === "peak_hz" ? " Hz" : k === "mag" ? (s === "acc" ? " g" : "") : " %");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function currentFlange() { return flanges.find((f) => f.flange_id === $("selFlange").value) || null; }

function renderFlanges(source) {
  const sel = $("selFlange");
  sel.innerHTML = flanges.map((f) => `<option value="${esc(f.flange_id)}">${esc(f.flange_id)} · ${esc(f.zone || "")}</option>`).join("");
  const last = store.g("last_flange", "");
  if (flanges.some((f) => f.flange_id === last)) sel.value = last;
  renderBolts();
  if (source === "demo") notice("시험 모드: Firebase 설정(web/firebase-config.js)이 없어서 가짜 플랜지로 동작해요. 기록은 서버에 올라가지 않아요.");
  else if (source === "cache") notice("인터넷이 없어서 기기에 저장해 둔 플랜지 목록을 쓰고 있어요.");
  else if (source === "none") notice("플랜지 목록을 못 불러왔어요. 인터넷에 연결한 상태로 앱을 한 번 열어 주세요 (이후에는 인터넷 없이도 돼요).");
  else notice("");
}
function renderBolts() {
  const f = currentFlange();
  const n = f ? f.bolt_count : 0;
  const sel = $("selBolt");
  sel.innerHTML = Array.from({ length: n }, (_, i) => `<option>B${String(i + 1).padStart(2, "0")}</option>`).join("");
  const last = store.g("last_bolt", "");
  if ([...sel.options].some((o) => o.value === last)) sel.value = last;
  renderRefInfo(); renderMetrics(); renderHist();
}
function renderRefInfo() {
  const f = currentFlange();
  if (!f) { $("refInfo").textContent = ""; return; }
  if (!f.tap_ref) { $("refInfo").textContent = "⚠ 이 플랜지는 정상 기준이 없어요. 대시보드에서 '정상 기준 등록'을 먼저 하세요."; return; }
  const acc = f.tap_ref.acc ? "음향+진동" : "음향만 (진동 기준 없음)";
  $("refInfo").textContent = `정상 기준: ${refSourceText(f.tap_ref)} · ${acc}`;
}
function renderMetrics() {
  const f = currentFlange(), bolt = $("selBolt").value;
  $("mTarget").textContent = f ? `${f.flange_id}-${bolt}` : "-";
  $("mSensor").textContent = f && f.tap_ref ? (f.tap_ref.acc ? "음향 + 진동" : "음향") : "-";
  $("mRef").textContent = f && f.tap_ref ? `실측 n=${f.tap_ref.n}` : "기준 없음";
  $("mCount").textContent = `${hitCount} 회`;
}

function renderChips() {
  const st = link ? link.state : "idle";
  const c = $("chipBle");
  c.className = "chip " + (st === "connected" ? "on" : "off");
  c.textContent = { idle: "블루투스 끊김", connecting: "연결 중…", connected: "블루투스 연결됨", reconnecting: "다시 연결 중…" }[st];
  $("chipNet").textContent = navigator.onLine ? "온라인" : "오프라인";
  $("chipNet").className = "chip " + (navigator.onLine ? "on" : "off");
  const p = pendingCount();
  $("chipPend").hidden = p === 0;
  $("chipPend").textContent = `전송 대기 ${p}건`;
  const btn = $("btnConnect");
  btn.textContent = st === "connected" ? "연결됨 · 끊기" : st === "idle" ? (hasSavedDevice() ? "블루투스 다시 연결" : "블루투스 연결") : "연결 중… (누르면 취소)";
  $("btnPick").hidden = !(isNative() && hasSavedDevice() && st === "idle");
}

function tileHtml(s, res, checks) {
  const lines = KEYS.map((k) => `${label(s, k)} ${checks[k] ? "✓" : "✕"}`).join(" &nbsp;|&nbsp; ");
  return `<div class="tile ${res}"><div class="tt">${TITLE[s]}</div><div class="tr">${ICON[res]} ${RESULT_KO[res]}</div><div class="tl">${lines}</div></div>`;
}

function renderResult() {
  const c = current;
  $("waitCard").hidden = !!c;
  $("resultCard").hidden = !c;
  renderMetrics();
  if (!c) return;
  const tp = c.tapping, ref = c.flange && c.flange.tap_ref;
  $("banner").className = "banner " + (tp ? tp.result : "");
  $("bTitle").textContent = `${c.flange ? c.flange.flange_id : "-"}-${c.bolt} 종합 판정`;
  $("bText").textContent = tp ? `${ICON[tp.result]} ${RESULT_KO[tp.result]}` : "○ 판정 불가";
  $("bSub").textContent = tp ? `범위를 벗어난 특징값 ${tp.score}개 · 기준: ${tp.ref_source}` + (c.saved ? " · 저장됨" : " · 저장 안 됨") : c.reason || "";
  $("simBanner").hidden = !c.isSim;
  $("warnSat").hidden = !(c.features.mic && c.features.mic.mag >= 0.98);

  let html = "";
  for (const s of ["mic", "acc"]) {
    const f = c.features[s], r = ref && ref[s];
    let col;
    if (!f) col = `<div class="tile none"><div class="tt">${TITLE[s]}</div><div class="tr">${NAME[s]} 센서 데이터 없음</div></div>`;
    else if (!r) {
      col = `<div class="tile none"><div class="tt">${TITLE[s]}</div><div class="tr">값은 들어왔지만 정상 기준이 없어 판정 제외</div></div>` +
        KEYS.map((k) => `<div class="g"><div class="gl">${label(s, k)}</div><div class="gb"></div><div class="gv">${valText(s, k, f[k])}</div></div>`).join("");
    } else {
      col = tileHtml(s, tp.sensor_results[s], tp.checks[s]) +
        KEYS.map((k) => gaugeHtml(label(s, k), f[k], r[k][0], r[k][1], gUnit(s, k), valText(s, k, f[k]))).join("");
    }
    html += `<div>${col}</div>`;
  }
  $("sensors").innerHTML = html;

  $("ruleText").textContent =
    "센서 2개(음향 INMP441, 진동 MPU6050)마다 특징값 3개(Peak Frequency, Peak Magnitude, Band Energy)를\n" +
    "정상 기준 범위와 비교해서, 범위를 벗어난 개수로 센서별 판정\n" +
    "  벗어난 개수 0개 → 정상 / 1개 → 재측정 필요 / 2개 이상 → 체결 이상 의심\n" +
    "종합 판정 = 두 센서 중 더 나쁜 쪽 (한 센서만 이상해도 종합이 나빠짐)\n" +
    `정상 범위 = 정상 샘플 평균 ± k × 표준편차   (지금 k = ${ref ? ref.k_sigma : "-"})`;

  let rows = "<tr><th>센서</th><th>특징값</th><th>하한</th><th>상한</th><th>이번 측정값</th><th>결과</th></tr>";
  for (const s of ["mic", "acc"]) for (const k of KEYS) {
    const r = ref && ref[s], f = c.features[s], v = f ? f[k] : null;
    const res = !r ? "기준 없음" : v === null ? "-" : (r[k][0] <= v && v <= r[k][1] ? "범위 안" : "범위 밖");
    rows += `<tr><td>${NAME[s]}</td><td>${label(s, k)}</td><td class="num">${r ? r[k][0] : "-"}</td><td class="num">${r ? r[k][1] : "-"}</td>` +
      `<td class="num">${v === null ? "-" : v}</td><td class="${res === "범위 안" ? "in" : res === "범위 밖" ? "out" : ""}">${res}</td></tr>`;
  }
  $("refTable").innerHTML = rows;

  $("btnSave").disabled = !tp || c.saved || c.isSim;
  $("btnSave").textContent = c.saved ? "✔ 저장됨" : "💾 저장";
}

function renderHist() {
  const f = $("selFlange").value, b = $("selBolt").value;
  $("histTitle").textContent = `${f}-${b} 검사 이력 (이 기기에서 저장한 것)`;
  const h = getHist().filter((x) => x.flange_id === f && x.bolt_id === b).slice(0, 15);
  $("histEmpty").hidden = h.length > 0;
  $("hist").innerHTML = h.length ? "<tr><th>시간</th><th>검사자</th><th>판정</th><th>음향 Peak(Hz)</th><th>진동 Peak(Hz)</th><th>이탈 수</th><th>기준</th><th>전송</th></tr>" +
    h.map((x) => {
      const t = new Date(x.at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
      const st = x.test ? "시험(서버 없음)" : x.sent ? "전송 완료" : "전송 대기";
      return `<tr><td>${t}</td><td>${esc(x.inspector || "-")}</td><td><span class="badge ${x.result}">${RESULT_KO[x.result]}</span></td>` +
        `<td class="num">${x.mic_peak != null ? x.mic_peak.toFixed(1) : "-"}</td><td class="num">${x.acc_peak != null ? x.acc_peak.toFixed(1) : "-"}</td>` +
        `<td class="num">${x.score ?? "-"}</td><td class="state">${esc(x.ref || "-")}</td><td class="state">${st}</td></tr>`;
    }).join("") : "";
  renderChips();
}

// ---------- 타격 수신 ----------
function onLine(line) {
  let msg;
  try { msg = JSON.parse(line); } catch { log("해석 못 한 글: " + line); return; }
  let features;
  try { features = featuresFromBle(msg); } catch (e) { log(`메시지 무시: ${e.message}`); return; }
  const flange = currentFlange();
  const bolt = $("selBolt").value;
  const isSim = msg.src === "sim";
  let tapping = null, reason = "";
  if (!flange) reason = "플랜지를 먼저 고르세요.";
  else if (!flange.tap_ref) reason = "이 플랜지는 정상 기준이 없어요. 대시보드에서 '정상 기준 등록'을 먼저 하세요.";
  else {
    tapping = tappingFromFeatures(features, flange.tap_ref, refSourceText(flange.tap_ref));
    if (!tapping) reason = "정상 기준과 맞는 센서 값이 없어서 판정할 수 없어요.";
  }
  hitCount++;
  current = { features, tapping, flange, bolt, isSim, saved: false, reason, msg };
  log(`타격 #${msg.seq ?? "-"} (${msg.src ?? "?"}) → ${tapping ? RESULT_KO[tapping.result] : "판정 불가"}`);
  renderResult();
  link.sendLed(tapping ? tapping.result : "OFF");        // ESP32 의 초록·빨강 LED 켜기
  if (tapping && !isSim && $("chkAuto").checked) doSave();
}

function doSave() {
  const c = current;
  if (!c || !c.tapping || c.saved || c.isSim) return;
  const inspector = $("inpInspector").value.trim();
  const deviceId = $("inpDevice").value.trim();
  if (!inspector || inspector.length > 20) { notice("검사자 이름을 1~20자로 적어 주세요. (위의 '검사자 · 기기 이름')"); $("inpInspector").closest("details").open = true; return; }
  if (!deviceId) { notice("기기 이름을 적어 주세요. 예: TAB-01"); $("inpDevice").closest("details").open = true; return; }
  store.s("inspector", inspector); store.s("device", deviceId);
  const taken = new Set(getHist().map((h) => h.id));
  const rec = makeRecord({
    flangeId: c.flange.flange_id, boltId: c.bolt, inspector, deviceId, tapping: c.tapping,
    isTaken: (id) => taken.has(id),
  });
  const errs = validateInspection(rec);
  if (errs.length) { notice("저장할 수 없어요: " + errs.join("; ")); log("스키마 오류: " + errs.join("; ")); return; }
  notice("");
  saveInspection(rec);
  c.saved = true;
  log(`저장: ${rec.record_id} (${hasServer ? navigator.onLine ? "서버로 전송 중" : "인터넷 없음 → 기기에 보관" : "시험 모드"})`);
  renderResult(); renderHist();
}

// ---------- 버튼 ----------
async function toggleConnect(pick = false) {
  const st = link.state;
  if (st === "connected" || st === "connecting" || st === "reconnecting") { await link.disconnect(); return; }
  try { if (pick) forgetDevice(); await link.connect({ pick }); }
  catch (e) {
    const m = e && e.message ? e.message : String(e);
    log("연결 실패: " + m);
    if (!/cancel|취소|chosen|선택/i.test(m)) notice("블루투스 연결 실패: " + m + " (ESP32 전원과 'TAP-01' 이름을 확인하세요)");
  }
}

function boot() {
  initStore();
  $("inpInspector").value = store.g("inspector", "");
  $("inpDevice").value = store.g("device", "TAB-01");
  link = new TapLink({
    onLine,
    onLog: log,
    onState: (s) => { link.state = s; renderChips(); },
  });
  link.state = "idle";

  $("btnConnect").onclick = () => toggleConnect(false);
  $("btnPick").onclick = () => toggleConnect(true);
  let ledTest = 0;                                       // 누를 때마다 정상 → 재측정 → 이상 → 끔 순서로 LED 시험
  $("btnLed").onclick = () => {
    if (link.state !== "connected") { notice("먼저 블루투스를 연결하세요."); return; }
    const m = ["OK", "CHECK", "NG", "OFF"][ledTest++ % 4];
    notice(`LED 시험: ${m}`);
    link.sendLed(m);
  };
  $("btnSave").onclick = doSave;
  $("btnNext").onclick = () => {
    link.sendLed("OFF");
    const sel = $("selBolt");
    sel.selectedIndex = (sel.selectedIndex + 1) % sel.options.length;
    store.s("last_bolt", sel.value);
    renderMetrics(); renderHist();
    log(`다음 볼트: ${sel.value}`);
  };
  $("selFlange").onchange = () => { store.s("last_flange", $("selFlange").value); renderBolts(); };
  $("selBolt").onchange = () => { store.s("last_bolt", $("selBolt").value); renderMetrics(); renderHist(); };
  window.addEventListener("online", renderChips);
  window.addEventListener("offline", renderChips);
  onHistChange(renderHist);

  if (!bleSupported()) notice("이 브라우저는 블루투스를 지원하지 않아요. 안드로이드 앱이나 PC·안드로이드 크롬을 쓰세요 (사파리·아이폰은 안 돼요).");
  if (!Capacitor.isNativePlatform() && "serviceWorker" in navigator && /^https?:$/.test(location.protocol)) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  renderChips(); renderHist(); renderResult();
  const reload = (why) => loadFlanges().then(({ list, source }) => {
    flanges = list; renderFlanges(source); log(`플랜지 ${list.length}개 (${source}${why ? " · " + why : ""})`);
  });
  reload("");
  $("btnReload").onclick = () => { notice("기준을 다시 불러오는 중…"); reload("수동"); };
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && hasServer) reload("화면 복귀"); });
}
boot();
