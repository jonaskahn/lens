<template>
  <Button
    :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
    severity="secondary"
    text
    rounded
    :aria-label="isDark ? 'Switch to day scope' : 'Switch to night scope'"
    @click="toggle"
  />
</template>

<script setup lang="ts">
const { isDark, toggle } = useDarkMode();
</script>
