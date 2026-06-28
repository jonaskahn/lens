import Aura from "@primeuix/themes/aura";
import { definePreset } from "@primeuix/themes";

/**
 * Periwinkle primary (oklch hue ~275) on a warm-neutral "antique parchment"
 * surface ramp (hue ~286, low chroma). Matches the daisyUI Light theme supplied
 * for the marketing site so the app and site share one identity.
 */
const LensPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: "oklch(97% 0.012 274.713)",
      100: "oklch(94% 0.024 274.713)",
      200: "oklch(90% 0.046 274.713)",
      300: "oklch(86% 0.072 274.713)",
      400: "oklch(78% 0.115 274.713)",
      500: "oklch(72% 0.115 274.713)",
      600: "oklch(64% 0.115 274.713)",
      700: "oklch(55% 0.115 274.713)",
      800: "oklch(46% 0.090 274.713)",
      900: "oklch(37% 0.068 274.713)",
      950: "oklch(28% 0.048 274.713)",
    },
    colorScheme: {
      light: {
        primary: {
          color: "{primary.700}",
          contrastColor: "#FFFFFF",
          hoverColor: "{primary.800}",
          activeColor: "{primary.900}",
        },
        highlight: {
          background: "{primary.50}",
          focusBackground: "{primary.100}",
          color: "{primary.700}",
          focusColor: "{primary.800}",
        },
        surface: {
          0: "oklch(100% 0 0)",
          50: "oklch(98% 0 0)",
          100: "oklch(96% 0.001 286.375)",
          200: "oklch(92% 0.004 286.32)",
          300: "oklch(86% 0.005 286.32)",
          400: "oklch(70% 0.006 285.885)",
          500: "oklch(55% 0.006 285.885)",
          600: "oklch(40% 0.006 285.885)",
          700: "oklch(28% 0.006 285.885)",
          800: "oklch(21% 0.006 285.885)",
          900: "oklch(14% 0.005 285.823)",
          950: "oklch(8% 0 0)",
        },
        formField: {
          background: "#FFFFFF",
          borderColor: "{surface.300}",
          hoverBorderColor: "{primary.400}",
          focusBorderColor: "{primary.600}",
        },
      },
      dark: {
        primary: {
          color: "{primary.300}",
          contrastColor: "oklch(14% 0.005 285.823)",
          hoverColor: "{primary.200}",
          activeColor: "{primary.100}",
        },
        highlight: {
          background: "color-mix(in oklch, {primary.400} 18%, transparent)",
          focusBackground: "color-mix(in oklch, {primary.400} 26%, transparent)",
          color: "{primary.200}",
          focusColor: "{primary.100}",
        },
        surface: {
          0: "oklch(20% 0.005 285.823)",
          50: "oklch(22% 0.005 285.823)",
          100: "oklch(24% 0.005 285.823)",
          200: "oklch(32% 0.006 285.885)",
          300: "oklch(42% 0.006 285.885)",
          400: "oklch(58% 0.006 285.885)",
          500: "oklch(72% 0.006 285.885)",
          600: "oklch(85% 0.004 286.32)",
          700: "oklch(92% 0.004 286.32)",
          800: "oklch(96% 0.001 286.375)",
          900: "oklch(98% 0 0)",
          950: "oklch(99% 0 0)",
        },
        formField: {
          background: "{surface.100}",
          borderColor: "{surface.300}",
          hoverBorderColor: "{primary.500}",
          focusBorderColor: "{primary.400}",
        },
      },
    },
  },
});

export default LensPreset;
