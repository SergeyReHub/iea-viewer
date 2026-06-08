import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const proxyTarget = env.VITE_DEV_API_PROXY || "http://127.0.0.1:8010";

  return {
    envDir: "..",
    plugins: [vue()],
    server: {
      host: "0.0.0.0",
      port: Number(env.VITE_DEV_PORT || 5180),
      strictPort: false,
      watch: {
        usePolling: true
      },
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyReq, req) => {
              const remoteAddress = req.socket.remoteAddress;
              if (!remoteAddress) {
                return;
              }
              const normalized = remoteAddress.startsWith("::ffff:")
                ? remoteAddress.slice("::ffff:".length)
                : remoteAddress;
              proxyReq.setHeader("X-Forwarded-For", normalized);
              proxyReq.setHeader("X-Real-IP", normalized);
            });
          }
        }
      }
    }
  };
});
