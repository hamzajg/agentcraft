/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      colors: {
        surface:  '#0e1117',
        panel:    '#161b24',
        border:   '#262d3a',
        muted:    '#4a5568',
        accent:   '#7c6fcd',
        'accent-dim': '#2d2657',
        amber:    '#f59e0b',
        'amber-dim': '#2d2200',
        teal:     '#10b981',
        'teal-dim': '#052e1c',
        danger:   '#ef4444',
      },
      animation: {
        'pulse-slow': 'pulse 2.4s cubic-bezier(0.4,0,0.6,1) infinite',
        'fade-in':    'fadeIn 0.18s ease-out',
        'slide-up':   'slideUp 0.22s ease-out',
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
