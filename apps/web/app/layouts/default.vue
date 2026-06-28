<template>
  <div class="shell graticule">
    <AppTopbar />
    <div class="shell__body">
      <AppSidebar />
      <main class="shell__main">
        <slot />
      </main>
    </div>
    <Toast position="bottom-right" />
    <ConfirmDialog />
  </div>
</template>

<script setup lang="ts">
// read color mode so the html class binding persists client-side hydration
useDarkMode();
</script>

<style scoped>
.shell {
  min-height: 100vh;
  background: var(--lens-ground);
  color: var(--lens-ink);
}
.shell__body {
  display: flex;
  align-items: stretch;
}
.shell__main {
  flex: 1;
  min-width: 0;
  padding: clamp(1.25rem, 0.75rem + 2vw, 2.5rem);
}
</style>
