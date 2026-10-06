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

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
await build({
  entryPoints: [resolve(app, "app.js")], outfile: resolve(out, "app.js"),
  bundle: true, format: "esm", target: ["chrome100"], minify: true, loader: { ".json": "json" }, logLevel: "warning",
});
for (const f of ["index.html", "style.css", "manifest.webmanifest"]) cpSync(resolve(app, f), resolve(out, f));
cpSync(resolve(app, "icons"), resolve(out, "icons"), { recursive: true });
writeFileSync(resolve(out, "sw.js"), readFileSync(resolve(app, "sw.js"), "utf8").replace("__BUILD__", String(Date.now())));
console.log("www/ 빌드 완료");
