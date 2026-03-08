import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = (env.VITE_API_PROXY_TARGET || "http://localhost:8000").trim();
  // Keep localhost as default for local development.
  // For AWS/remote access set VITE_DEV_HOST=0.0.0.0 or pass --host 0.0.0.0.
  const devHost = (env.VITE_DEV_HOST || "localhost").trim();
  const devPort = Number(env.VITE_DEV_PORT || 5173);

  return {
    plugins: [react()],
    server: {
      host: devHost,
      port: devPort,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/assets": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
