import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react({ include: /\.[jt]sx?$/ })],
  server: {
    port: 5173,
    proxy: {
      "/upload": "http://127.0.0.1:5000",
      "/reports": "http://127.0.0.1:5000",
      "/health": "http://127.0.0.1:5000",
      "/sample-data": "http://127.0.0.1:5000",
      "/api": "http://127.0.0.1:5000",
    },
  },
  esbuild: {
    loader: "jsx",
    include: /\.[jt]sx?$/,
    exclude: [/node_modules/],
  },
});
