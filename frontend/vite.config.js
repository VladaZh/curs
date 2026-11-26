import { defineConfig } from 'vite'
import { resolve } from 'path'

const service = (port) => ({
  target: `http://localhost:${port}`,
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/api\/[a-z]+/, ''),
})

export default defineConfig({
  base: process.env.CI_GITHUB_ACTIONS ? '/restaurants/' : '/',
  server: {
    proxy: {
      '/api/identity': service(8002),
      '/api/catalog': service(8001),
      '/api/booking': service(8000),
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        restaurant: resolve(__dirname, 'restaurant.html'),
        auth: resolve(__dirname, 'auth.html'),
        bookings: resolve(__dirname, 'bookings.html'),
      },
    },
    outDir: 'dist',
    assetsDir: 'assets',
  },
})