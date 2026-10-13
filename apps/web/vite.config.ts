import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // Require valid remote production licensing API URL for production release builds
  if (mode === "production") {
    const licUrl = env.VITE_LICENSING_API_URL;
    if (!licUrl || licUrl.includes("127.0.0.1") || licUrl.includes("localhost")) {
      throw new Error(
        `[Vite Build Error] Production release requires VITE_LICENSING_API_URL to point to a valid remote licensing server URL, but got "${licUrl || ""}". Set VITE_LICENSING_API_URL in .env.production or environment variables.`
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
      port: 5173,
      host: "127.0.0.1",
      proxy: {
        "/api": {
          target: "http://127.0.0.1:38291",
          changeOrigin: true,
        },
        "/health": {
          target: "http://127.0.0.1:38291",
          changeOrigin: true,
        },
      },
    },
  };
});
