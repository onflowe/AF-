import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5000,
    fs: {
      allow: ['..']
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
  base: '/',
  publicDir: 'public'
});
