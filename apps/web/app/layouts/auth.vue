<template>
  <div class="auth graticule">
    <CornerMarks />
    <slot />
    <Toast position="bottom-right" />
  </div>
</template>

<script setup lang="ts">
useDarkMode();
</script>

<style scoped>
.auth {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1.25rem;
  background: var(--lens-ground);
  position: relative;
}
</style>
