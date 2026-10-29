const C="io-v5",A=["./","index.html","app.js","capa/mock.js","capa/odoo.js","css/app.css","datos/checklist.json","datos/guia.json","manifest.webmanifest","iconos/icon.svg"];
self.addEventListener("install",e=>e.waitUntil(caches.open(C).then(c=>c.addAll(A))));
self.addEventListener("fetch",e=>e.respondWith(fetch(e.request).catch(()=>caches.match(e.request))));
