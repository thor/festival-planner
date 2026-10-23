import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The API has no CORS, so dev serves it same-origin through a proxy.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/graphql": process.env.FESTIVAL_PLANNER_API ?? "http://127.0.0.1:8000",
    },
  },
})
