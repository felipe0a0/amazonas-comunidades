const CACHE = "amazonas-comunidade-final-v1";
const PREFIXO_APP = "/app/";
const ARQUIVOS = [
  "/app/index.html", "/app/comunidade.html", "/app/relatorio.html", "/app/acompanhar.html",
  "/app/instituicao_login.html", "/app/instituicao.html", "/app/mapa.html", "/app/sobre.html", "/app/ajudar.html",
  "/app/style.css", "/app/common.js", "/app/script.js", "/app/comunidade.js", "/app/relatorio.js", "/app/acompanhar.js",
  "/app/instituicao_login.js", "/app/instituicao.js", "/app/mapa.js", "/app/icon-192.png", "/app/icon-512.png", "/app/manifest.json"
];
self.addEventListener("install", event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ARQUIVOS))); self.skipWaiting(); });
self.addEventListener("activate", event => { event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))), self.clients.claim()])); });
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(PREFIXO_APP)) return;
  event.respondWith(fetch(event.request).then(response => { if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));}return response; }).catch(()=>caches.match(event.request)));
});
