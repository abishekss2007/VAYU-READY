import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0f2545", 700: "#16335e", 600: "#1d4079", 900: "#0a1a31" },
        sky: { accent: "#0ea5e9" },
        ok: "#16a34a",
        warn: "#d97706",
        crit: "#dc2626",
      },
      fontFamily: {
        // System fonts only: nothing is fetched from the internet.
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Noto Sans", "Noto Sans Devanagari", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
