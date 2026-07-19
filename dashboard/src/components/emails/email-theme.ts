import { pixelBasedPreset, type TailwindConfig } from "react-email";

export const emailTailwindConfig = {
  presets: [pixelBasedPreset],
  theme: {
    extend: {
      colors: {
        canvas: "#070709",
        surface: "#0e0e12",
        surfaceRaised: "#15151b",
        line: "#292932",
        primary: "#f7f7f9",
        secondary: "#a4a4ad",
        muted: "#74747e",
        accent: "#829cff",
        accentSoft: "#aab9ff",
        ink: "#08090d",
      },
    },
  },
} satisfies TailwindConfig;
