import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import type { ProxyOptions } from "vite";
/** Strip Secure / Domain from Set-Cookie so browsers accept cookies on http://127.0.0.1:5173 */
function devApiProxy(target: string): ProxyOptions {
  return {
    target,
    changeOrigin: true,
    secure: false,
    configure: (proxy) => {
      proxy.on("proxyRes", (proxyRes) => {
        const raw = proxyRes.headers["set-cookie"];
        if (!raw) return;
        const list = Array.isArray(raw) ? raw : [raw];
        proxyRes.headers["set-cookie"] = list.map((cookie) =>
          cookie
            .replace(/;\s*Secure/gi, "")
            .replace(/;\s*Domain=[^;]*/gi, "")
        );
      });
    },
  };
}

function streamApiProxy(target: string): ProxyOptions {
  return {
    target,
    changeOrigin: true,
    secure: false,
    configure: (proxy) => {
      proxy.on("proxyRes", (proxyRes) => {
        delete proxyRes.headers["content-length"];
        proxyRes.headers["cache-control"] = "no-cache, no-transform";
        proxyRes.headers["x-accel-buffering"] = "no";
        proxyRes.headers["connection"] = "keep-alive";
      });
    },
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/designer/chat/stream": streamApiProxy("http://127.0.0.1:8000"),
      "/api": devApiProxy("http://127.0.0.1:8000"),
      "/media": devApiProxy("http://127.0.0.1:8000"),
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
