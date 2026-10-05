/**
 * Build config for `npm run test:render` — the plan UI rendered under Node.
 *
 * Two things differ from the application build, and both matter:
 *
 *   `copyPublicDir: false` — the render check needs no images or videos, and
 *   writing a copy of public/ is not just wasteful: a running dev server
 *   watches this project, and a freshly written video file inside it makes
 *   that watcher fail with EBUSY on Windows.
 *
 *   `outDir: node_modules/.render-check` — Vite does not watch node_modules,
 *   so the output cannot disturb a dev server that is already running. It is
 *   also already gitignored.
 */

import { defineConfig } from "vite";

export default defineConfig({
  build: {
    ssr: "src/test/renderPlanUI.jsx",
    outDir: "node_modules/.render-check",
    emptyOutDir: true,
    copyPublicDir: false,
  },
});
