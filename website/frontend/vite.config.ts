import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendTarget = (process.env.VITE_API_BASE ?? process.env.AEGIS_BACKEND_URL ?? 'http://127.0.0.1:8787').replace(
  /\/+$/,
  ''
);

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'icon-vendor': ['lucide-react']
        }
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true
      }
    }
  }
});
