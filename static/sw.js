// sw.js - Service Worker for 即动 PWA

const CACHE_NAME = "jidong-v1";
const STATIC_ASSETS = [
  "/static/style.css",
  "/static/manifest.json",
];

// ── 安装：缓存静态资源 ──────────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn("[SW] Pre-cache failed:", err);
      });
    })
  );
  self.skipWaiting();
});

// ── 激活：清理旧缓存 ─────────────────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch：Cache First for static, Network First for API ────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API 请求：总是走网络，失败则返回 JSON 错误
  if (url.pathname.startsWith("/api/") || event.request.method !== "GET") {
    return;
  }

  // 静态资源：Cache First
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((resp) => {
          if (resp && resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return resp;
        });
      })
    );
    return;
  }

  // HTML 页面：Network First，断网时尝试缓存
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        if (resp && resp.status === 200) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return resp;
      })
      .catch(() => {
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          return caches.match("/").then((fallback) => {
            return fallback || new Response(
              "<h2 style='font-family:sans-serif;padding:40px;color:#40916C'>暂时无法连接，请检查网络后重试</h2>",
              { headers: { "Content-Type": "text/html; charset=utf-8" } }
            );
          });
        });
      })
  );
});

// ── 推送通知（久坐提醒预留接口）─────────────────────────────────────────────
self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || "即动提醒";
  const options = {
    body: data.body || "久坐太久了，起来活动一下吧！",
    icon: "/static/manifest.json",
    badge: "/static/manifest.json",
    vibrate: [200, 100, 200],
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === targetUrl && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(targetUrl);
    })
  );
});
