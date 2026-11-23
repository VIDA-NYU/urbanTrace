import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // autk-map is linked from a local Autark checkout (see package.json), which lives outside this folder.
  server: { fs: { allow: ['..', '../../autark'] } },
  // Keep the Autark packages out of dependency pre-bundling, as Autark's own gallery does.
  optimizeDeps: { exclude: ['@urban-toolkit/autk-map', '@urban-toolkit/autk-core'] },
})
