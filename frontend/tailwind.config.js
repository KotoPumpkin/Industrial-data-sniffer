/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        heading: ['Bahnschrift', 'DIN Alternate', 'Segoe UI', 'system-ui', 'sans-serif'],
        body: ['PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', 'sans-serif'],
        data: ['Bahnschrift', 'DIN Alternate', 'Consolas', 'monospace'],
        kpi: ['Bahnschrift', 'DIN Alternate', 'Consolas', 'monospace'],
      },
      colors: {
        canvas: '#080b10',
        panel: '#0f1218',
        'panel-header': '#161a22',
        sidebar: '#0c0f14',
        input: '#161a22',
        hover: '#1c2029',
        border: '#232830',
        'border-light': '#2d333b',
        blue: { DEFAULT: '#3b82f6', dim: '#1e3a5f' },
        green: { DEFAULT: '#34d399', dark: '#0d3320' },
        orange: { DEFAULT: '#fb923c', dark: '#3d2410' },
        red: { DEFAULT: '#f87171', dark: '#3b1515' },
        cyan: '#22d3ee',
      },
    },
  },
  plugins: [],
}
