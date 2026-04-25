import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./types/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        riskLow: "#2e8b57",
        riskMedium: "#f2b134",
        riskHigh: "#c43302"
      }
    }
  },
  plugins: []
}

export default config
