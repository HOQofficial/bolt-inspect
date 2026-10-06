// 크롬에서 '홈 화면에 추가'로 설치해 쓸 때, 인터넷이 없어도 앱이 열리게 파일을 기기에 보관함.
// (안드로이드 앱 안에서는 파일이 앱에 들어 있으므로 쓰이지 않음)
const CACHE = "bolt-app-__BUILD__";
const FILES = ["./", "index.html", "app.js", "style.css", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;   // Firebase 통신은 건드리지 않음
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request)));
});
