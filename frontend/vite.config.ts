import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5000,
    fs: {
      allow: ['..']
    }
  },
  base: '/',
  publicDir: 'public'
});
