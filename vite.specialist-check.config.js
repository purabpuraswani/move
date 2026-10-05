import { defineConfig } from "vite";

export default defineConfig({
  build: {
    ssr: "src/test/renderSpecialistDetailCheck.jsx",
    outDir: "node_modules/.render-check-specialist",
    emptyOutDir: true,
    copyPublicDir: false,
  },
});
