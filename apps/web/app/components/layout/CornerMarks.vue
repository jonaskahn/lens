<template>
  <div class="corner-marks" aria-hidden="true">
    <span v-for="i in 4" :key="i" :class="`corner corner--${i}`" />
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.corner-marks {
  position: absolute;
  inset: 1.5rem;
  pointer-events: none;
}
.corner {
  position: absolute;
  width: 1.25rem;
  height: 1.25rem;
  border-color: var(--lens-primary);
  border-style: solid;
  border-width: 0;
  opacity: 0.7;
}
.corner--1 { top: 0; left: 0; border-top-width: 1px; border-left-width: 1px; }
.corner--2 { top: 0; right: 0; border-top-width: 1px; border-right-width: 1px; }
.corner--3 { bottom: 0; left: 0; border-bottom-width: 1px; border-left-width: 1px; }
.corner--4 { bottom: 0; right: 0; border-bottom-width: 1px; border-right-width: 1px; }
</style>
