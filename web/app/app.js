// 볼트 타음 검사 앱 화면 (탭 4개: 측정 / 기준 등록 / 기록 / 설정).
// 흐름: 버튼을 누르면 ESP32 가 솔레노이드로 한 번 치고 1회만 측정 -> 특징값·FFT 를 받아 정상 기준과 비교 -> 저장.
// 소리가 날 때마다 자동 측정하지 않음 (Firebase 한도 절약). 'evt:miss' 는 소리를 못 들었다는 뜻.
import { Capacitor } from "@capacitor/core";
import { featuresFromBle, spectrumFromBle, calcTapRef } from "../schema.js";
import { TapLink, bleSupported, hasSavedDevice, forgetDevice, isNative } from "./ble.js";
import { tappingFromFeatures, refSourceText, makeRecord, RESULT_KO } from "./judge.js";
import { validateInspection, validateTapRef } from "./validate.js";
import { gaugeCompactHtml } from "./gauge.js";
import { spectrumHtml } from "./spectrum.js";
import {
  initStore, hasServer, loadFlanges, saveInspection, getHist, onHistChange, pendingCount,
  getSamples, setSamples, getUsedKeys, addUsedKeys, saveTapRef,
} from "./store.js";

const $ = (id) => document.getElementById(id);
const store = (() => {                       // 설정값 기억. 막혀 있어도 앱은 동작
  const g = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
  const s = (k, v) => { try { localStorage.setItem(k, v); } catch { /* 무시 */ } };
  return { g, s };
})();

let flanges = [];
let current = null;          // 측정 탭의 가장 최근 결과 { features, spectrum, tapping, flange, bolt, saved, reason, key }
let lastReg = null;          // 기준 등록 탭의 가장 최근 측정 { features, spectrum, key, at }
let link = null;
let tab = "measure";
let pending = null;          // { kind: "strike" | "hand", timer }
const seenKeys = [];         // 방금 받은 측정 키 (같은 메시지가 두 번 오는 것 방지)

// ---------- 글자·표시 도우미 ----------
function log(m) {
  const t = new Date().toLocaleTimeString("ko-KR", { hour12: false });
  $("log").textContent = `${t}  ${m}\n` + $("log").textContent.slice(0, 4000);
}
function notice(text) { $("notice").textContent = text || ""; $("notice").hidden = !text; }
const UNIT = { mic: { peak_hz: "Hz", mag: "", energy_pct: "%" }, acc: { peak_hz: "Hz", mag: "g", energy_pct: "%" } };
const NAME = { mic: "음향", acc: "진동" };
const PART = { mic: "INMP441", acc: "MPU6050" };
const LABEL = { peak_hz: "Peak 주파수", mag: "Peak 크기", energy_pct: "대역 에너지" };
const KEYS = ["peak_hz", "mag", "energy_pct"];
const IC = {
  mic: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4"/></svg>',
  acc: '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="2 12 6 12 9 5 15 19 18 12 22 12"/></svg>',
  OK: '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="5 13 10 18 19 7"/></svg>',
  CHECK: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><line x1="12" y1="10" x2="12" y2="14"/><line x1="12" y1="17" x2="12" y2="17.1"/></svg>',
  NG: '<svg viewBox="0 0 24 24" aria-hidden="true"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>',
};
const fmt = (k, v) => (k === "peak_hz" ? Number(v).toFixed(0) : k === "mag" ? Number(v).toFixed(3) : Number(v).toFixed(1));
const unitText = (s, k) => (UNIT[s][k] ? ` ${UNIT[s][k]}` : "");
const valText = (s, k, v) => `${fmt(k, v)}${unitText(s, k)}`;
const rangeNum = (k, v) => (k === "peak_hz" ? Number(v).toFixed(0) : k === "mag" ? Number(v).toFixed(2) : Number(v).toFixed(1));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const connected = () => !!link && link.state === "connected";

function currentFlange() { return flanges.find((f) => f.flange_id === $("selFlange").value) || null; }

// ---------- 탭 ----------
function setTab(name) {
  tab = name;
  document.querySelectorAll(".tab").forEach((el) => { el.hidden = el.id !== `tab-${name}`; });
  document.querySelectorAll(".tabbtn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $("target").hidden = !(name === "measure" || name === "register");
  if (name === "history") renderHist();
  if (name === "register") renderRegister();
  window.scrollTo(0, 0);
}

// ---------- 플랜지·볼트 ----------
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
  renderRefInfo(); renderRefTable(); renderHist();
  if (tab === "register") renderRegister();
}
function renderRefInfo() {
  const f = currentFlange();
  if (!f) { $("refInfo").textContent = ""; return; }
  if (!f.tap_ref) { $("refInfo").textContent = "⚠ 이 플랜지는 정상 기준이 아직 없어요 → '기준 등록' 탭에서 먼저 등록하세요."; return; }
  const acc = f.tap_ref.acc ? "음향+진동" : "음향만";
  $("refInfo").textContent = `정상 기준: ${refSourceText(f.tap_ref)} · ${acc}`;
}

function renderChips() {
  const st = link ? link.state : "idle";
  const c = $("chipBle");
  c.className = "chip " + (st === "connected" ? "on" : "off");
  c.textContent = { idle: "끊김", connecting: "연결 중…", connected: "연결됨", reconnecting: "재연결 중…" }[st];
  $("chipNet").textContent = navigator.onLine ? "온라인" : "오프라인";
  $("chipNet").className = "chip " + (navigator.onLine ? "on" : "off");
  const p = pendingCount();
  $("chipPend").hidden = p === 0;
  $("chipPend").textContent = `전송 대기 ${p}건`;
  const btn = $("btnConnect");
  btn.textContent = st === "connected" ? "연결됨 · 끊기" : st === "idle" ? (hasSavedDevice() ? "블루투스 다시 연결" : "블루투스 연결") : "연결 중… (누르면 취소)";
  btn.classList.toggle("primary", st !== "connected");
  $("btnPick").hidden = !(isNative() && hasSavedDevice() && st === "idle");
  const on = st === "connected";
  $("actions").hidden = !on;
  for (const id of ["btnRegStrike", "btnRegHand"]) $(id).disabled = !on || !!pending;
  for (const id of ["btnStrike", "btnHand"]) $(id).disabled = !!pending;
  $("regConnHint").hidden = on;
  if (!on) clearPending();
}

// ---------- 타격 요청 · 대기 상태 ----------
function setStatus(text, cls = "") {
  for (const el of [$("statusLine"), $("regStatus")]) if (el) { el.textContent = text; el.className = "statusline " + cls; }
}
function clearPending() {
  if (pending) { clearTimeout(pending.timer); pending = null; }
  for (const id of ["btnStrike", "btnHand"]) $(id).disabled = false;
  for (const id of ["btnRegStrike", "btnRegHand"]) $(id).disabled = !connected();
}
async function request(kind) {
  if (!connected()) { notice("먼저 블루투스를 연결하세요."); return; }
  if (pending) return;
  if (tab === "measure") {
    const f = currentFlange();
    if (!f) { notice("플랜지를 먼저 고르세요."); return; }
    if (!f.tap_ref) { notice("이 플랜지는 정상 기준이 없어요 → '기준 등록' 탭에서 먼저 등록하세요."); return; }
  }
  const ok = kind === "strike" ? await link.sendStrike() : await link.sendHandArm();
  if (!ok) { setStatus("명령을 못 보냈어요. 연결을 확인하세요.", "bad"); return; }
  for (const id of ["btnStrike", "btnHand", "btnRegStrike", "btnRegHand"]) $(id).disabled = true;
  setStatus(kind === "strike" ? "치는 중… 소리를 기다려요" : "지금 볼트를 치세요 (8초 안에)", "busy");
  pending = {
    kind,
    timer: setTimeout(() => { clearPending(); setStatus("응답이 없어요. 다시 눌러 보세요 (ESP32 펌웨어·전원 확인).", "bad"); }, 12000),
  };
}

// ---------- 측정 결과 (측정 탭) ----------
function sensorCard(s, c, ref) {
  const f = c.features[s], r = ref && ref[s], tp = c.tapping;
  if (!f) return `<div class="sc"><div class="sc-head"><div class="sc-name">${IC[s]}${NAME[s]} <small>${PART[s]}</small></div><span class="badge none">데이터 없음</span></div><div class="sc-none">${NAME[s]} 센서 값이 들어오지 않았어요.</div></div>`;
  const res = tp && r ? tp.sensor_results[s] : null;
  let html = `<div class="sc"><div class="sc-head"><div class="sc-name">${IC[s]}${NAME[s]} <small>${PART[s]}</small></div>` +
    `<span class="badge ${res || "none"}">${res ? RESULT_KO[res] : "기준 없음"}</span></div>`;
  if (!r) {
    html += `<div class="sc-none">정상 기준이 없어 판정에서 제외했어요.<br>` + KEYS.map((k) => `${LABEL[k]} ${valText(s, k, f[k])}`).join(" · ") + `</div>`;
  } else {
    html += KEYS.map((k) => gaugeCompactHtml(LABEL[k], f[k], r[k][0], r[k][1], unitText(s, k), valText(s, k, f[k]),
      `정상 ${rangeNum(k, r[k][0])} ~ ${rangeNum(k, r[k][1])}${unitText(s, k)}`)).join("");
  }
  const tr = c.spectrum && c.spectrum[s];
  if (tr) {
    html += `<div class="fft"><div class="fft-t"><span>FFT 그래프</span><i>0 ~ ${tr.f_max >= 1000 ? tr.f_max / 1000 + " kHz" : tr.f_max + " Hz"}</i></div>` +
      spectrumHtml(tr, f.peak_hz, r ? r.peak_hz : null, NAME[s]) +
      `<div class="legend"><span>정상 Peak 범위</span><span class="pk">이번 Peak</span></div></div>`;
  }
  return html + `</div>`;
}

function renderResult() {
  const c = current;
  $("waitCard").hidden = !!c;
  $("resultCard").hidden = !c;
  if (!c) return;
  const tp = c.tapping, ref = c.flange && c.flange.tap_ref;
  $("hero").className = "hero " + (tp ? tp.result : "");
  $("heroIc").innerHTML = tp ? IC[tp.result] : "?";
  $("heroSub").textContent = `${c.flange ? c.flange.flange_id : "-"}-${c.bolt} 종합 판정`;
  $("heroRes").textContent = tp ? RESULT_KO[tp.result] : "판정 불가";
  $("heroMeta").textContent = tp
    ? `범위 밖 특징 ${tp.score}개 · ${tp.ref_source} · ${c.saved ? "저장됨" : "저장 안 됨"}`
    : c.reason || "";
  $("warnSat").hidden = !(c.features.mic && c.features.mic.mag >= 0.98);
  $("sensors").innerHTML = ["mic", "acc"].map((s) => sensorCard(s, c, ref)).join("");
  $("btnSave").disabled = !tp || c.saved;
  $("btnSave").textContent = c.saved ? "✔ 저장됨" : "💾 저장";
}

// ---------- 설정 탭의 규칙·기준표 ----------
function renderRefTable() {
  const ref = currentFlange() && currentFlange().tap_ref;
  $("ruleText").textContent =
    "센서 2개(음향 INMP441, 진동 MPU6050)마다 특징값 3개(Peak 주파수, Peak 크기, 대역 에너지)를\n" +
    "정상 기준 범위와 비교해서, 범위를 벗어난 개수로 센서별 판정\n" +
    "  벗어난 개수 0개 → 정상 / 1개 → 재측정 필요 / 2개 이상 → 체결 이상 의심\n" +
    "종합 판정 = 두 센서 중 더 나쁜 쪽\n" +
    `정상 범위 = 정상 샘플 평균 ± k × 표준편차   (지금 k = ${ref ? ref.k_sigma : "-"})`;
  let rows = "<tr><th>센서</th><th>특징값</th><th>하한</th><th>상한</th></tr>";
  for (const s of ["mic", "acc"]) for (const k of KEYS) {
    const r = ref && ref[s];
    rows += `<tr><td>${NAME[s]}</td><td>${LABEL[k]}</td><td class="num">${r ? r[k][0] : "-"}</td><td class="num">${r ? r[k][1] : "-"}</td></tr>`;
  }
  $("refTable").innerHTML = rows;
}

// ---------- 기록 탭 ----------
function renderHist() {
  const h = getHist().slice(0, 30);
  $("histEmpty").hidden = h.length > 0;
  $("hist").innerHTML = h.map((x) => {
    const t = new Date(x.at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
    const st = x.test ? "시험(서버 없음)" : x.sent ? "전송 완료" : "전송 대기";
    return `<div class="hrow"><span class="badge ${x.result}">${RESULT_KO[x.result]}</span>` +
      `<div class="m">${esc(x.flange_id)}-${esc(x.bolt_id)}<small>${t} · ${esc(x.inspector || "-")} · ${st}</small></div>` +
      `<div class="t">${x.mic_peak != null ? x.mic_peak.toFixed(0) : "-"} Hz</div></div>`;
  }).join("");
  renderChips();
}

// ---------- 기준 등록 탭 ----------
const regTarget = () => Number($("regTarget").value) || 10;
const regK = () => Number($("regK").value) || 3;

function sampleLine(x) {
  const part = (s) => (x[s] ? `${NAME[s]} ${x[s].peak_hz.toFixed(0)} Hz · ${x[s].mag.toFixed(2)}${s === "acc" ? " g" : ""} · ${x[s].energy_pct.toFixed(0)}%` : "");
  return [part("mic"), part("acc")].filter(Boolean).join("<br>");
}

function renderRegister() {
  const f = currentFlange();
  const list = f ? getSamples(f.flange_id) : [];
  const n = list.length, target = regTarget();
  $("regBar").style.width = `${Math.min(100, (n / target) * 100)}%`;
  $("regCount").textContent = `${n} / ${target}`;
  $("regListN").textContent = n ? `(${n}개)` : "";
  $("regList").innerHTML = list.map((x, i) =>
    `<div class="sample"><span class="no">${i + 1}</span><div class="vv">${sampleLine(x)}<br><small>${esc(String(x.key).slice(-14))}</small></div>` +
    `<button type="button" data-del="${i}" aria-label="${i + 1}번 샘플 지우기">✕</button></div>`).join("");
  $("regList").querySelectorAll("[data-del]").forEach((b) => { b.onclick = () => removeSample(Number(b.dataset.del)); });

  // 방금 측정한 값
  const used = lastReg && new Set([...getUsedKeys(), ...list.map((x) => x.key)]).has(lastReg.key);
  if (!lastReg) {
    $("regLast").innerHTML = `<div>아직 측정한 값이 없어요. 위의 <b>타격 + 측정</b>을 누르세요.</div>`;
  } else {
    const sat = lastReg.features.mic && lastReg.features.mic.mag >= 0.98;
    let h = "";
    for (const s of ["mic", "acc"]) {
      const v = lastReg.features[s];
      if (!v) continue;
      h += `<div class="tag">${NAME[s]} · ${PART[s]}</div><div class="vals">` +
        KEYS.map((k) => `<div class="val"><span>${LABEL[k]}</span><b>${fmt(k, v[k])}</b></div>`).join("") + `</div>`;
    }
    if (sat) h += `<div class="dup">소리가 너무 커서 잘렸어요(크기 ≈ 1). 정상 샘플로 넣을 수 없어요 → 더 약하게 치거나 마이크를 떨어뜨리세요.</div>`;
    else if (used) h += `<div class="dup">이미 추가한 측정이에요. (같은 측정은 한 번만 들어가요)</div>`;
    $("regLast").innerHTML = h;
  }
  $("btnAddSample").disabled = !lastReg || used || !f || (lastReg && lastReg.features.mic && lastReg.features.mic.mag >= 0.98);

  // 평균·범위 미리보기
  if (n >= 3) {
    try {
      const r = calcTapRef(list, regK());
      let t = `<table><tr><th>센서</th><th>특징값</th><th>평균 ± ${regK()}σ 범위</th></tr>`;
      for (const s of ["mic", "acc"]) for (const k of KEYS) if (r[s]) {
        t += `<tr><td>${NAME[s]}</td><td>${LABEL[k]}</td><td class="num">${rangeNum(k, r[s][k][0])} ~ ${rangeNum(k, r[s][k][1])}${unitText(s, k)}</td></tr>`;
      }
      $("regPreview").innerHTML = t + "</table>";
      $("btnRegSave").disabled = false;
    } catch (e) { $("regPreview").textContent = e.message; $("btnRegSave").disabled = true; }
  } else {
    $("regPreview").textContent = n ? `${3 - n}개 더 모으면 평균과 정상 범위가 계산돼요.` : "";
    $("btnRegSave").disabled = true;
  }
  $("btnRegClear").disabled = n === 0;
}

function addSample() {
  const f = currentFlange();
  if (!f || !lastReg) return false;
  const list = getSamples(f.flange_id);
  const used = new Set([...getUsedKeys(), ...list.map((x) => x.key)]);
  if (used.has(lastReg.key)) { notice("이미 추가한 측정이에요."); return false; }
  const m = lastReg.features;
  if (m.mic && m.mic.mag >= 0.98) { notice("소리가 잘린 측정은 정상 샘플로 넣을 수 없어요."); return false; }
  if (list.length && !!list[0].acc !== !!m.acc) { notice("앞선 샘플과 센서 구성이 달라요(진동 값 유무). 샘플을 비우고 같은 방식으로 다시 모으세요."); return false; }
  if (list.length >= 50) { notice("샘플은 최대 50개까지예요."); return false; }
  notice("");
  list.push({ key: lastReg.key, at: lastReg.at, mic: m.mic || null, acc: m.acc || null });
  setSamples(f.flange_id, list);
  renderRegister();
  return true;
}
function removeSample(i) {
  const f = currentFlange();
  if (!f) return;
  const list = getSamples(f.flange_id);
  list.splice(i, 1);
  setSamples(f.flange_id, list);
  renderRegister();
}
async function saveRef() {
  const f = currentFlange();
  if (!f) return;
  const list = getSamples(f.flange_id);
  let ref;
  try { ref = calcTapRef(list, regK()); } catch (e) { notice(e.message); return; }
  const errs = validateTapRef(ref);
  if (errs.length) { notice("기준을 저장할 수 없어요: " + errs.join("; ")); log("기준 스키마 오류: " + errs.join("; ")); return; }
  const msg = f.tap_ref
    ? `${f.flange_id} 에는 이미 정상 기준(${refSourceText(f.tap_ref)})이 있어요.\n새 기준(n=${ref.n})으로 덮어쓸까요?`
    : `${f.flange_id} 의 정상 기준을 샘플 ${ref.n}개로 저장할까요?`;
  if (!confirm(msg)) return;
  $("btnRegSave").disabled = true;
  try {
    const { flange, queued } = await saveTapRef(f, ref);
    flanges = flanges.map((x) => (x.flange_id === f.flange_id ? flange : x));
    addUsedKeys(list.map((x) => x.key));
    setSamples(f.flange_id, []);
    lastReg = null;
    renderRefInfo(); renderRefTable(); renderRegister();
    notice(queued ? "기준을 기기에 저장했어요. 인터넷이 연결되면 서버에 올라가요." : (hasServer ? "정상 기준을 저장했어요. PC 대시보드에도 반영돼요." : "시험 모드라 이 화면에서만 적용돼요."));
    log(`정상 기준 저장: ${f.flange_id} n=${ref.n} k=${ref.k_sigma}`);
  } catch (e) {
    notice("기준 저장 실패: " + (e.message || e) + " (Firestore 규칙에서 flanges 쓰기가 허용돼 있어야 해요)");
    log("기준 저장 실패: " + (e.message || e));
    renderRegister();
  }
}

// ---------- 측정 수신 ----------
function onLine(line) {
  let msg;
  try { msg = JSON.parse(line); } catch { log("해석 못 한 글: " + line); return; }
  if (msg.evt === "miss") {                       // 시간 안에 소리가 안 들림
    clearPending();
    setStatus("소리를 못 들었어요. 마이크 위치·솔레노이드 타격을 확인하고 다시 누르세요.", "bad");
    log("측정 시간 초과(소리 없음)");
    return;
  }
  let features;
  try { features = featuresFromBle(msg); } catch (e) { log(`메시지 무시: ${e.message}`); return; }
  const key = msg.k || `${msg.seq ?? "x"}-${Date.now()}`;
  if (seenKeys.includes(key)) { log(`같은 측정(${key}) 중복 수신 → 무시`); return; }
  seenKeys.push(key); if (seenKeys.length > 50) seenKeys.shift();
  const spectrum = spectrumFromBle(msg);
  clearPending();
  setStatus("측정 완료 · 다시 측정하려면 버튼을 누르세요");

  if (tab === "register") {                       // 기준 등록 중에는 판정·저장하지 않음
    lastReg = { features, spectrum, key, at: new Date().toISOString() };
    log(`기준용 측정 ${key}`);
    if ($("chkRegAuto").checked) addSample();
    renderRegister();
    return;
  }
  const flange = currentFlange();
  const bolt = $("selBolt").value;
  let tapping = null, reason = "";
  if (!flange) reason = "플랜지를 먼저 고르세요.";
  else if (!flange.tap_ref) reason = "이 플랜지는 정상 기준이 없어요 → '기준 등록' 탭에서 등록하세요.";
  else {
    tapping = tappingFromFeatures(features, flange.tap_ref, refSourceText(flange.tap_ref), spectrum);
    if (!tapping) reason = "정상 기준과 맞는 센서 값이 없어서 판정할 수 없어요.";
  }
  current = { features, spectrum, tapping, flange, bolt, saved: false, reason, key };
  log(`측정 ${key} → ${tapping ? RESULT_KO[tapping.result] : "판정 불가"}`);
  renderResult();
  link.sendLed(tapping ? tapping.result : "OFF");        // ESP32 의 초록·빨강 LED
  if (tapping && $("chkAuto").checked) doSave();
}

function doSave() {
  const c = current;
  if (!c || !c.tapping || c.saved) return;
  const inspector = $("inpInspector").value.trim();
  const deviceId = $("inpDevice").value.trim();
  if (!inspector || inspector.length > 20) { notice("검사자 이름을 1~20자로 적어 주세요. (설정 탭)"); setTab("settings"); return; }
  if (!deviceId) { notice("기기 이름을 적어 주세요. 예: TAB-01 (설정 탭)"); setTab("settings"); return; }
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

function fillSelect(id, values, selected, suffix = "") {
  $(id).innerHTML = values.map((v) => `<option value="${v}">${v}${suffix}</option>`).join("");
  $(id).value = String(selected);
}

function boot() {
  initStore();
  $("inpInspector").value = store.g("inspector", "");
  $("inpDevice").value = store.g("device", "TAB-01");
  $("chkAuto").checked = store.g("auto_save", "1") === "1";
  $("chkRegAuto").checked = store.g("reg_auto", "0") === "1";
  fillSelect("regTarget", [5, 10, 15, 20], store.g("reg_target", "10"), "회");
  fillSelect("regK", [2, 2.5, 3, 4], store.g("reg_k", "3"), "σ");

  link = new TapLink({
    onLine,
    onLog: log,
    onState: (s) => { link.state = s; renderChips(); },
  });
  link.state = "idle";

  document.querySelectorAll(".tabbtn").forEach((b) => { b.onclick = () => setTab(b.dataset.tab); });
  $("btnConnect").onclick = () => toggleConnect(false);
  $("btnPick").onclick = () => toggleConnect(true);
  $("btnStrike").onclick = () => request("strike");
  $("btnHand").onclick = () => request("hand");
  $("btnRegStrike").onclick = () => request("strike");
  $("btnRegHand").onclick = () => request("hand");
  let ledTest = 0;                                       // 누를 때마다 정상 → 재측정 → 이상 → 끔 순서
  $("btnLed").onclick = () => {
    if (!connected()) { notice("먼저 블루투스를 연결하세요."); return; }
    const m = ["OK", "CHECK", "NG", "OFF"][ledTest++ % 4];
    notice(`LED 시험: ${m}`);
    link.sendLed(m);
  };
  $("btnSave").onclick = doSave;
  $("btnNext").onclick = () => {
    if (connected()) link.sendLed("OFF");
    const sel = $("selBolt");
    sel.selectedIndex = (sel.selectedIndex + 1) % sel.options.length;
    store.s("last_bolt", sel.value);
    current = null; renderResult();
    setStatus(`다음 볼트 ${sel.value} · 버튼을 눌러 측정하세요`);
    log(`다음 볼트: ${sel.value}`);
  };
  $("selFlange").onchange = () => { store.s("last_flange", $("selFlange").value); current = null; lastReg = null; renderResult(); renderBolts(); };
  $("selBolt").onchange = () => store.s("last_bolt", $("selBolt").value);
  $("chkAuto").onchange = () => store.s("auto_save", $("chkAuto").checked ? "1" : "0");
  $("chkRegAuto").onchange = () => store.s("reg_auto", $("chkRegAuto").checked ? "1" : "0");
  $("regTarget").onchange = () => { store.s("reg_target", $("regTarget").value); renderRegister(); };
  $("regK").onchange = () => { store.s("reg_k", $("regK").value); renderRegister(); };
  $("btnAddSample").onclick = addSample;
  $("btnRegSave").onclick = saveRef;
  $("btnRegClear").onclick = () => {
    const f = currentFlange();
    if (f && confirm("모은 샘플을 모두 지울까요?")) { setSamples(f.flange_id, []); renderRegister(); }
  };
  window.addEventListener("online", renderChips);
  window.addEventListener("offline", renderChips);
  onHistChange(renderHist);

  if (!bleSupported()) notice("이 브라우저는 블루투스를 지원하지 않아요. 안드로이드 앱이나 PC·안드로이드 크롬을 쓰세요 (사파리·아이폰은 안 돼요).");
  if (!Capacitor.isNativePlatform() && "serviceWorker" in navigator && /^https?:$/.test(location.protocol)) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  setTab("measure");
  renderChips(); renderHist(); renderResult();
  const reload = (why) => loadFlanges().then(({ list, source }) => {
    flanges = list; renderFlanges(source); log(`플랜지 ${list.length}개 (${source}${why ? " · " + why : ""})`);
  });
  reload("");
  $("btnReload").onclick = () => { notice("기준을 다시 불러오는 중…"); reload("수동"); };
  document.addEventListener("visibilitychange", () => {
    // 샘플을 모으는 중이거나 기준을 방금 저장했다면 서버값으로 덮어쓰지 않도록 기준 등록 탭에서는 다시 읽지 않음
    if (document.visibilityState === "visible" && hasServer && tab !== "register") reload("화면 복귀");
  });
}
boot();
