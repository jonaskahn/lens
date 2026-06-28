import LensPreset from "./app/assets/theme";

export default defineNuxtConfig({
  modules: [
    "@primevue/nuxt-module",
    "@pinia/nuxt",
    "@vueuse/nuxt",
    "@nuxt/image",
    "@nuxt/eslint",
    "@nuxt/test-utils/module",
  ],

  components: {
    dirs: [
      { path: "~~/app/components", pathPrefix: false, extensions: ["vue"] },
    ],
  },

  css: ["primeicons/primeicons.css", "~/assets/css/main.css"],

  primevue: {
    autoImport: true,
    options: {
      ripple: true,
      theme: {
        preset: LensPreset,
        options: {
          darkModeSelector: ".p-dark",
          cssLayer: {
            name: "primevue",
            order: "theme, base, primevue, components, utilities",
          },
        },
      },
    },
  },

  runtimeConfig: {
    apiBaseUrl: "",
    apiKey: "",
    sessionPassword: "",
    public: {
      appName: "lens",
    },
  },

  devtools: { enabled: true },

  compatibilityDate: "2025-06-27",
});
