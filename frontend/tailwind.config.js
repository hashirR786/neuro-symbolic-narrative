/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0d1117",
          800: "#1a1a2e",
          700: "#16213e",
          600: "#0f3460",
        },
        accent: {
          green:  "#4CAF50",
          blue:   "#2196F3",
          orange: "#FF9800",
          purple: "#9C27B0",
          red:    "#F44336",
          pink:   "#FF1744",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
