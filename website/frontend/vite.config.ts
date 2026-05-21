import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendTarget = (process.env.VITE_API_BASE ?? process.env.AEGIS_BACKEND_URL ?? 'http://127.0.0.1:8787').replace(
  /\/+$/,
  ''
);

export default defineConfig({
  base: '/chatbot/',
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const moduleId = id.replaceAll('\\', '/');
          if (moduleId.includes('/node_modules/react/') || moduleId.endsWith('/node_modules/react/index.js')) {
            return 'react-vendor';
          }
          if (moduleId.includes('/node_modules/react-dom/')) {
            return 'react-vendor';
          }
          if (moduleId.includes('/node_modules/lucide-react/')) {
            return 'icon-vendor';
          }
          if (moduleId.includes('/src/api.ts')) {
            return 'app-api';
          }
          if (moduleId.includes('/src/utils/') || moduleId.includes('/src/styles/appStyles.ts')) {
            return 'app-support';
          }
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
