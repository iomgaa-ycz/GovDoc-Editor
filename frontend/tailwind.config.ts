import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#F7F8FA", card: "#FFFFFF" },
        sidebar: { DEFAULT: "#0A0F1E", hover: "#131B2E", active: "#0D1525" },
        accent: { DEFAULT: "#0062FF", hover: "#2563EB", light: "#F0F5FF" },
        border: { DEFAULT: "#E5E7EB", light: "#F3F4F6" },
        text: { primary: "#1A1A1A", secondary: "#4B5563", muted: "#9CA3AF", inverse: "#FFFFFF" },
        status: {
          ok: "#16A34A", "ok-bg": "#F0FDF4",
          warn: "#D97706", "warn-bg": "#FFFBEB",
          err: "#DC2626", "err-bg": "#FEF2F2", "err-border": "#FECACA",
          info: "#3B82F6", "info-bg": "#EFF6FF",
        },
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["Geist Mono", "monospace"] },
      borderRadius: { btn: "6px", card: "8px", modal: "12px" },
      width: { sidebar: "240px" },
      boxShadow: { card: "0 1px 3px rgba(0,0,0,0.06)", modal: "0 8px 32px rgba(0,0,0,0.12)" },
    },
  },
  plugins: [],
};

export default config;
