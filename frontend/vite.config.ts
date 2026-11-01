import { defineConfig } from 'vite';

export default defineConfig({
  build: { rollupOptions: { input: {game: 'index.html', admin: 'admin.html'} } },
  server: { proxy: {
    '/api': 'http://127.0.0.1:7079',
    '/admin/api': 'http://127.0.0.1:7079',
  } },
});
