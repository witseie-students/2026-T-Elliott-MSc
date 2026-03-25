// tailwind.config.js
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Heading font — geometric sans, academic weight
        grotesk: ["'Space Grotesk'", "sans-serif"],
        // Label / monospace font — retro-block feel
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
}
