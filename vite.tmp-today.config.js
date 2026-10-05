/** TEMPORARY build config for the Today screen render check. Deleted after use. */

import { defineConfig } from "vite";

export default defineConfig({
  build: {
    ssr: "src/test/tmpRenderToday.jsx",
    outDir: "node_modules/.tmp-today",
    emptyOutDir: true,
    copyPublicDir: false,
  },
});
