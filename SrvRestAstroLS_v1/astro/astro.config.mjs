import { defineConfig } from "astro/config";
import svelte from "@astrojs/svelte";
import tailwindcss from "@tailwindcss/vite";

const backendDevTarget = "http://127.0.0.1:7008";

export default defineConfig({
  integrations: [svelte()],
  devToolbar: { enabled: false },
  server: {
    host: "127.0.0.1",
    port: 3008,
  },
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: backendDevTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  },
});
