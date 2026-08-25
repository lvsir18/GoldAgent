import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)", surface: "var(--surface)", line: "var(--line)",
        ink: "var(--ink)", muted: "var(--muted)", gold: "var(--gold)",
        positive: "var(--positive)", negative: "var(--negative)", warning: "var(--warning)"
      }
    }
  },
  plugins: []
} satisfies Config;
