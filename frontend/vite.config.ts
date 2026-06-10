import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/login': 'http://localhost:5000',
      '/register': 'http://localhost:5000',
      '/admin': 'http://localhost:5000',
    },
  },
  build: {
    outDir: '../manager/static',
    emptyOutDir: true,
  },
});
