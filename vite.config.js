import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Vite does not read PORT on its own, so an assigned port would be
    // ignored and it would try 5173 anyway. Honour PORT when the host
    // sets one; fall back to the usual 5173 for a plain `npm run dev`.
    port: process.env.PORT ? Number(process.env.PORT) : 5173,
  },
})
