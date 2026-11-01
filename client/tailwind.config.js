export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        emerald: {
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
        },
        surface: {
          50: '#0a0f0a',
          100: '#0d140d',
          200: '#0f1a0f',
          300: '#111a11',
          400: '#1a2e1a',
          500: '#1f3a1f',
        }
      }
    }
  },
  plugins: []
}
