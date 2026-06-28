<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>

<script setup lang="ts">
// Bind dark class to <html> in one place; layouts/components use useDarkMode() to read + toggle it.
useDarkMode();

useHead({
  htmlAttrs: { lang: "en" },
  titleTemplate: (titleChunk) => (titleChunk ? `${titleChunk} — lens` : "lens — change watch console"),
  link: [
    { rel: "preconnect", href: "https://fonts.googleapis.com" },
    { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "" },
    {
      rel: "stylesheet",
      href: "https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400..700;1,6..96,400..600&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap",
    },
  ],
  meta: [
    { name: "viewport", content: "width=device-width, initial-scale=1" },
    { name: "color-scheme", content: "light dark" },
    { name: "description", content: "lens — a watch console for tracked pages: crawl, diff, classify, notify." },
  ],
});
</script>
