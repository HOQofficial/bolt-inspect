// 크롬에서 '홈 화면에 추가'로 설치해 쓸 때, 인터넷이 없어도 앱이 열리게 파일을 기기에 보관함.
// (안드로이드 앱 안에서는 파일이 앱에 들어 있으므로 쓰이지 않음)
// 인터넷이 되면 항상 최신 파일을 받고(받은 것을 보관), 인터넷이 없을 때만 보관해 둔 것을 씀.
const CACHE = "bolt-app-__BUILD__";
const FILES = ["./", "index.html", "app.js", "style.css", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];
// cache: "reload" = 브라우저가 쉬어 둔 옛 사본을 쓰지 않고 서버에서 새로 받음 (배포했는데 옛 화면이 남는 문제 방지)
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES.map((f) => new Request(f, { cache: "reload" })))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;   // Firebase 통신은 건드리지 않음
  e.respondWith(
    fetch(e.request, { cache: "no-cache" })
      .then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
