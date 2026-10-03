;/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        abyss: '#04122A',       // deepest ocean navy
        midnight: '#0A1E3F',    // midnight blue surfaces
        deepsea: '#0E2A4D',     // slightly lighter panel base
        cyan: { caribbean: '#22D3EE', glow: '#67E8F9' },
        seaglass: '#7DE2C3',
        biolum: '#8B7CF6',      // restrained violet highlight
        warning: { amber: '#F59E0B', ember: '#F97316' },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
