import { defineConfig } from "vite";

export default defineConfig({
  build: {
    ssr: "src/test/renderSpecialistComponentsCheck.jsx",
    outDir: "node_modules/.render-check-components",
    emptyOutDir: true,
    copyPublicDir: false,
  },
});