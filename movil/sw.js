/* Servicio para usar SpiderFinance sin conexión. Sube VERSION al publicar cambios. */
const VERSION = "sf-1.1.0";
const SHELL = [
  "./", "index.html", "style.css", "app.js", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "icons/apple-touch-icon.png", "assets/logo.png",
  ...["estado_al_ras", "estado_falta_dinero", "estado_sobra_dinero", "estado_sin_datos", "racha_al_ras", "racha_falta_dinero", "racha_sobra_dinero",
      "seccion_ajustes", "seccion_historial", "seccion_ingresos", "seccion_juego", "seccion_objetivos", "seccion_obligaciones", "seccion_proyeccion"]
    .map(n => `assets/${n}.webp`),
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).catch(() => caches.match("index.html")))
  );
});
