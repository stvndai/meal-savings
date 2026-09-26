import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// This frontend needs no environment files; never let Vite load them.
export default defineConfig({ plugins: [react(), tailwindcss()], envDir: false, server: { host: '127.0.0.1', port: 5173, strictPort: true }, preview: { host: '127.0.0.1', port: 4173, strictPort: true } })
