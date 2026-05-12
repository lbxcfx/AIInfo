import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201b",
        field: "#f7f8f6",
        line: "#dfe5df",
        accent: "#276b5d",
        amber: "#b56f28",
      },
    },
  },
  plugins: [],
};

export default config;

