import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'What is in the freezer?',
        short_name: 'Tundra',
        description: 'Freezer inventory',
        theme_color: '#0e1a2b',
        background_color: '#0e1a2b',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
});
