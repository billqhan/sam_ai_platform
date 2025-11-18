import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'

export default defineConfig(({ mode }) => {
  // Load .env.dev from project root (one level up) for development mode
  const envFile = mode === 'development' ? '../.env.dev' : `.env.${mode}`;
  const envPath = new URL(envFile, import.meta.url).pathname;
  
  // Simple env file parser
  const env = {};
  try {
    // Handle both Unix and Windows paths
    const normalizedPath = process.platform === 'win32' ? envPath.substring(1) : envPath;
    const content = fs.readFileSync(normalizedPath, 'utf-8');
    content.split('\n').forEach(line => {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('export ')) {
        const equalsIndex = trimmed.indexOf('=');
        if (equalsIndex > 0) {
          const key = trimmed.substring(0, equalsIndex).trim();
          let value = trimmed.substring(equalsIndex + 1).trim();
          // Remove quotes if present
          if ((value.startsWith('"') && value.endsWith('"')) || 
              (value.startsWith("'") && value.endsWith("'"))) {
            value = value.substring(1, value.length - 1);
          }
          env[key] = value;
        }
      }
    });
    console.log('Loaded env from:', normalizedPath);
  } catch (e) {
    console.warn(`Could not load ${envFile}:`, e.message);
  }

  return {
    plugins: [react()],
    server: {
      port: 3000,
      // Only use proxy if no API_BASE_URL is configured
      proxy: env.VITE_API_BASE_URL ? {} : {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:4000',
          changeOrigin: true,
        }
      }
    },
    define: {
      // Inject env vars into the app
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(env.VITE_API_BASE_URL),
      'import.meta.env.VITE_API_URL': JSON.stringify(env.VITE_API_URL),
      'import.meta.env.VITE_AWS_REGION': JSON.stringify(env.VITE_AWS_REGION),
      'import.meta.env.VITE_ENVIRONMENT': JSON.stringify(env.VITE_ENVIRONMENT),
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            charts: ['recharts'],
          }
        }
      }
    }
  }
})
