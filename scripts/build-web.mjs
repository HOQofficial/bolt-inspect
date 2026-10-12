// web/app 을 한 파일로 묶어서 www/ 에 만든다 (안드로이드 앱과 인터넷 배포가 이 폴더를 씀).
// 사용: npm run build
import { build } from "esbuild";
import { existsSync, mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const web = resolve(root, "web");
const app = resolve(web, "app");
const out = resolve(root, "www");

// Firebase 설정 파일이 있으면 쓰고, 없으면 '시험 모드'(서버 없음)로 만든다.
const hasCfg = existsSync(resolve(web, "firebase-config.js"));
writeFileSync(resolve(app, "_config.js"),
  hasCfg ? 'export { firebaseConfig } from "../firebase-config.js";\n' : "export const firebaseConfig = null;\n");
console.log(hasCfg ? "Firebase 설정: web/firebase-config.js 사용" : "Firebase 설정 파일 없음 → 시험 모드로 빌드 (web/firebase-config.js 를 만들면 서버 저장이 켜져요)");

// 사용: npm run build            → 인터넷 배포용 (첫 화면 = 소개 페이지, 앱 = /app/)
//       npm run build -- --app-root → 안드로이드 앱용 (앱이 바로 첫 화면)
const appRoot = process.argv.includes("--app-root");
const dest = appRoot ? out : resolve(out, "app");
rmSync(out, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });
await build({
  entryPoints: [resolve(app, "app.js")], outfile: resolve(dest, "app.js"),
  bundle: true, format: "esm", target: ["chrome100"], minify: true, loader: { ".json": "json" }, logLevel: "warning",
});
for (const f of ["index.html", "style.css", "manifest.webmanifest"]) cpSync(resolve(app, f), resolve(dest, f));
cpSync(resolve(app, "icons"), resolve(dest, "icons"), { recursive: true });
writeFileSync(resolve(dest, "sw.js"), readFileSync(resolve(app, "sw.js"), "utf8").replace("__BUILD__", String(Date.now())));
if (!appRoot) {
  cpSync(resolve(web, "landing.html"), resolve(out, "index.html"));
  // 예전에 첫 화면(/)에 설치돼 있던 앱 캐시를 지우고 스스로 사라지는 파일 (없으면 옛 화면이 계속 보일 수 있음)
  writeFileSync(resolve(out, "sw.js"),
    'self.addEventListener("install",()=>self.skipWaiting());\n' +
    'self.addEventListener("activate",(e)=>e.waitUntil(caches.keys().then((ks)=>Promise.all(ks.map((k)=>caches.delete(k)))).then(()=>self.registration.unregister())));\n');
}
console.log(appRoot ? "www/ 빌드 완료 (앱 전용: 앱이 첫 화면)" : "www/ 빌드 완료 (소개 페이지 + www/app/ 앱)");
