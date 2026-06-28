import { useColorMode } from "@vueuse/core";

/**
 * Wires the dark-mode class onto <html> as `p-dark` so the whole document
 * (body, app chrome, PrimeVue components) flips together.
 */
export function useDarkMode() {
  const colorMode = useColorMode({
    selector: "html",
    attribute: "class",
    modes: {
      dark: "p-dark",
      light: "",
    },
    storageKey: "lens-color-mode",
  });
  const isDark = computed(() => colorMode.value === "dark");

  function toggle() {
    colorMode.value = isDark.value ? "light" : "dark";
  }

  return { colorMode, isDark, toggle };
}
