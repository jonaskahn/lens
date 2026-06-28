import { defineNuxtPlugin } from "#app";
import { VueQueryPlugin } from "@tanstack/vue-query";

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.use(VueQueryPlugin, {
    queryClientConfig: {
      defaultOptions: {
        queries: {
          staleTime: 30_000,
          retry: 1,
        },
      },
    },
  });
});
