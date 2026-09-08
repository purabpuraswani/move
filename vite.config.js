import { defineConfig } from 'vite'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] })
  ],
  resolve: {
    alias: {
      // `@tensorflow-models/pose-detection` statically imports
      // `{ Pose }` from `@mediapipe/pose` at the top level, but that
      // package ships a global script with no ES module exports, so
      // Rolldown fails dependency optimization with MISSING_EXPORT.
      // MoveWell only uses the MoveNet runtime and never constructs a
      // MediaPipe solution, so the specifier is redirected to a shim that
      // provides the export and throws if it is ever instantiated.
      '@mediapipe/pose': fileURLToPath(
        new URL('./src/shims/mediapipe-pose.js', import.meta.url)
      )
    }
  }
})
