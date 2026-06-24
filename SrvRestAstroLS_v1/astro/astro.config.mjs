import { defineConfig } from "astro/config";
import svelte from "@astrojs/svelte";
import tailwindcss from "@tailwindcss/vite";

const backendTarget =
  process.env.PUBLIC_TEBAAI_API_BASE_URL ?? "http://127.0.0.1:7008";

export default defineConfig({
  integrations: [svelte()],
  server: {
    host: "127.0.0.1",
    port: 3008,
  },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  },
});
