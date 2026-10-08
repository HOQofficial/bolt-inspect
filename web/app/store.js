// 플랜지 목록(정상 기준 포함) 읽기 + 검사 기록 저장.
//  - Firebase 설정(web/firebase-config.js)이 있으면 Firestore 에 저장. 인터넷이 없으면 기기에 쌓아 두었다가 연결되면 자동 업로드.
//  - 설정이 없으면 '시험 모드': 가짜 플랜지로 블루투스·판정만 시험하고 서버에는 아무것도 올리지 않음.
import { initializeApp } from "firebase/app";
import { initializeFirestore, persistentLocalCache, doc, setDoc, collection, getDocs, waitForPendingWrites } from "firebase/firestore";
import { nowKstIso } from "../schema.js";
import { firebaseConfig } from "./_config.js";

const LS_FLANGES = "bolt_flanges_v1";
const LS_HIST = "bolt_hist_v1";
const HIST_MAX = 200;
const LS_SAMPLES = "bolt_ref_samples_v1";     // 정상 기준 등록 중에 모아 둔 샘플 { 플랜지: [ ... ] }
const LS_USED = "bolt_ref_used_keys_v1";      // 이미 정상 샘플로 쓴 측정의 고유 키 (같은 측정을 또 넣지 않게)

export const hasServer = !!(firebaseConfig && firebaseConfig.apiKey && !String(firebaseConfig.apiKey).startsWith("여기에"));
let db = null;

// 시험 모드용 가짜 플랜지 (tools/sim.py 의 DEMO_REF 와 같은 값)
export const DEMO_FLANGE = {
  flange_id: "FL999", zone: "시험용(서버 없음)", bolt_spec: "M16", bolt_count: 4,
  tap_ref: {
    mic: { peak_hz: [3000, 3400], mag: [0.7, 0.9], energy_pct: [60, 80] },
    acc: { peak_hz: [400, 440], mag: [0.6, 0.82], energy_pct: [62, 82] },
    n: 10, k_sigma: 3, registered_at: "2026-10-05T09:30:00+09:00",
  },
};

const ls = {
  get(k, fallback) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* 저장 공간 부족 등 */ } },
};

export function initStore() {
  if (!hasServer) return;
  const app = initializeApp(firebaseConfig);
  db = initializeFirestore(app, { localCache: persistentLocalCache() });
  syncSent();
  window.addEventListener("online", syncSent);
}

// ---------- 플랜지 ----------
const withTimeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("시간 초과")), ms))]);

// 돌려주는 값: { list, source: "server" | "cache" | "demo" | "none" }
export async function loadFlanges() {
  if (!hasServer) return { list: [DEMO_FLANGE], source: "demo" };
  const pending = getDocs(collection(db, "flanges")).then((snap) => {
    const list = snap.docs.map((d) => d.data()).sort((a, b) => a.flange_id.localeCompare(b.flange_id));
    if (list.length) ls.set(LS_FLANGES, list);        // 다음에 인터넷이 없어도 쓰도록 기기에 복사
    return list;
  });
  try {
    const list = await withTimeout(pending, 6000);
    if (list.length) return { list, source: "server" };
  } catch { pending.catch(() => {}); }                // 늦게 도착해도 위에서 기기 복사본은 갱신됨
  const cached = ls.get(LS_FLANGES, []);
  return { list: cached, source: cached.length ? "cache" : "none" };
}

// ---------- 이 기기의 저장 기록 ----------
export const getHist = () => ls.get(LS_HIST, []);
const listeners = new Set();
export const onHistChange = (fn) => listeners.add(fn);
function setHist(h) { ls.set(LS_HIST, h.slice(0, HIST_MAX)); listeners.forEach((f) => f()); }
export const pendingCount = () => getHist().filter((h) => !h.sent && !h.test).length;

export function saveInspection(rec) {
  const item = {
    id: rec.record_id, at: rec.inspected_at, flange_id: rec.flange_id, bolt_id: rec.bolt_id,
    result: rec.final_result, sent: false, test: !hasServer,
    inspector: rec.inspector, score: rec.tapping.score, ref: rec.tapping.ref_source,
    mic_peak: rec.tapping.features.mic.peak_hz, acc_peak: rec.tapping.features.acc ? rec.tapping.features.acc.peak_hz : null,
  };
  setHist([item, ...getHist()]);
  if (!db) return "test";
  // await 하지 않음: 인터넷이 없으면 여기서 멈추지 않고, 연결되면 Firestore 가 알아서 올림
  setDoc(doc(db, "inspections", rec.record_id), rec)
    .then(() => markSent(rec.record_id))
    .catch((e) => console.warn("서버 저장 실패", e));
  return "queued";
}

function markSent(id) {
  setHist(getHist().map((h) => (h.id === id ? { ...h, sent: true } : h)));
}
function syncSent() {            // 앱을 껐다 켠 뒤에도 대기 중이던 기록이 올라갔는지 확인
  if (!db) return;
  waitForPendingWrites(db).then(() => setHist(getHist().map((h) => ({ ...h, sent: true })))).catch(() => {});
}

// ---------- 정상 기준 등록 ----------
// 모아 둔 정상 샘플 (플랜지마다 따로). 앱을 닫았다 열어도 남아 있음
export const getSamples = (flangeId) => (ls.get(LS_SAMPLES, {})[flangeId] || []);
export function setSamples(flangeId, list) { const all = ls.get(LS_SAMPLES, {}); all[flangeId] = list; ls.set(LS_SAMPLES, all); }
export const getUsedKeys = () => ls.get(LS_USED, []);
export function addUsedKeys(keys) { ls.set(LS_USED, [...new Set([...getUsedKeys(), ...keys])].slice(-500)); }

// 계산한 정상 기준을 플랜지 문서에 저장 (flanges/{id} 의 tap_ref, updated_at 만 바꿈).
// 돌려주는 값: { flange: 바뀐 플랜지, queued: 인터넷이 없어 올리기 대기 중이면 true }
export async function saveTapRef(flange, tapRef) {
  const updated_at = nowKstIso();
  const flangeNew = { ...flange, tap_ref: tapRef, updated_at };
  let queued = false;
  if (db) {
    const p = setDoc(doc(db, "flanges", flange.flange_id), { tap_ref: tapRef, updated_at }, { merge: true });
    try { await withTimeout(p, 8000); } catch (e) {
      if (!/시간 초과/.test(e.message)) throw e;       // 인터넷이 없으면 연결될 때 Firestore 가 알아서 올림
      queued = true; p.catch(() => {});
    }
    const cached = ls.get(LS_FLANGES, []);
    if (cached.length) ls.set(LS_FLANGES, cached.map((f) => (f.flange_id === flange.flange_id ? flangeNew : f)));
  }
  return { flange: flangeNew, queued };
}
