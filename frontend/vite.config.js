import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { visualizer } from 'rollup-plugin-visualizer'

function stripInvalidVueusePureAnnotations() {
  return {
    name: 'strip-invalid-vueuse-pure-annotations',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('@vueuse/core/dist/index.js')) {
        return null
      }

      const cleaned = code
        .replace(/\n\/\* #__PURE__ \*\/\nconst events =/g, '\nconst events =')
        .replace(/const defaultState = \(\/\* #__PURE__ \*\/\s*\{/g, 'const defaultState = ({')

      return cleaned === code ? null : { code: cleaned, map: null }
    }
  }
}

export default defineConfig(({ mode }) => {
  const analyzeBundle = mode === 'analyze' || process.env.BUNDLE_ANALYZE === 'true'
  const plugins = [stripInvalidVueusePureAnnotations(), vue()]

  if (analyzeBundle) {
    plugins.push(
      visualizer({
        filename: 'dist/bundle-stats.html',
        template: 'treemap',
        gzipSize: true,
        brotliSize: true
      }),
      visualizer({
        filename: 'dist/bundle-stats.json',
        template: 'raw-data',
        gzipSize: true,
        brotliSize: true
      })
    )
  }

  return {
    plugins,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: false,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              return undefined
            }

            if (id.includes('element-plus') || id.includes('@element-plus')) {
              return 'element-plus'
            }

            if (id.includes('zrender')) {
              return 'zrender'
            }

            if (id.includes('echarts')) {
              return 'echarts'
            }

            if (id.includes('vue') || id.includes('pinia')) {
              return 'vue-vendor'
            }

            if (id.includes('axios')) {
              return 'axios'
            }

            return 'vendor'
          }
        }
      }
    }
  }
})
