// www/ 를 http://localhost:8000 으로 열어 준다 (크롬에서 블루투스 시험용). 사용: npm run serve
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const www = resolve(dirname(fileURLToPath(import.meta.url)), "..", "www");
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".png": "image/png",
  ".webmanifest": "application/manifest+json", ".json": "application/json" };
createServer(async (req, res) => {
  const p = new URL(req.url, "http://x").pathname;
  const file = resolve(www, "." + (p === "/" ? "/index.html" : p));
  if (!file.startsWith(www)) { res.writeHead(403).end(); return; }
  try { const data = await readFile(file); res.writeHead(200, { "Content-Type": types[extname(file)] || "application/octet-stream" }); res.end(data); }
  catch { res.writeHead(404).end("not found"); }
}).listen(8000, () => console.log("열기: http://localhost:8000   (끄기: Ctrl + C)"));
