import { defineConfig, type UserConfig } from 'vite';
import {fileURLToPath} from 'node:url';
import {optimizeAssets} from './tools/optimized-assets';

export default defineConfig(async (): Promise<UserConfig> => {
  const assets = await optimizeAssets(fileURLToPath(new URL('./public/assets', import.meta.url)));
  return {
  define: {__ASSET_URLS__: JSON.stringify(assets)},
  plugins: [{name: 'optimized-css-images', enforce: 'pre', transform(code, id) {
    if (!id.endsWith('.css')) return;
    return code.replace(/url\((['"]?)(\/assets\/[^'"\s)]+)\1\)/g,
      (_match, _quote, path: string) => `url('${assets[path] ?? path}')`);
  }}],
  build: { rollupOptions: { input: {game: 'index.html', admin: 'admin.html'},
    output: {manualChunks: id => id.includes('/node_modules/phaser/') ? 'phaser' : undefined} } },
  server: { proxy: {
    '/api': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:7079',
    '^/admin/api/': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:7079',
  } },
  };
});
