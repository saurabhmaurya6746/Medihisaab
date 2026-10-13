import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const licensingApiUrl = env.VITE_LICENSING_API_URL || "";

  // Fail production builds if production licensing API URL is missing or points to localhost
  if (mode === "production") {
    if (!licensingApiUrl) {
      throw new Error(
        "[PRODUCTION BUILD ERROR] VITE_LICENSING_API_URL is required for production builds. " +
          "Configure it in .env.production with your canonical HTTPS licensing service URL."
      );
    }
    if (licensingApiUrl.includes("localhost") || licensingApiUrl.includes("127.0.0.1")) {
      throw new Error(
        `[PRODUCTION BUILD ERROR] VITE_LICENSING_API_URL cannot point to localhost in production: "${licensingApiUrl}". ` +
          "Use a public HTTPS domain (e.g., https://licensing.apexhealth.com)."
      );
    }
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@pharmacy/api-contracts": path.resolve(__dirname, "../../packages/api-contracts/src/index.ts"),
      },
    },
    server: {
      port: 5174,
      host: "127.0.0.1",
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/health": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/vendor": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/downloads": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
        "/MediHisaab-Setup-1.0.0.exe": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
