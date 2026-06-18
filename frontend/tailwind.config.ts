import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#5b6cff",
          fg: "#ffffff",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
