<template>
  <div class="nameplate">
    <div class="nameplate__lead">
      <div v-if="eyebrow || $slots.eyebrow" class="nameplate__eyebrow">
        <slot name="eyebrow">{{ eyebrow }}</slot>
      </div>
      <h1 class="nameplate__title">
        <slot name="title">{{ title }}</slot>
      </h1>
      <p v-if="$slots.default" class="nameplate__lede">
        <slot />
      </p>
    </div>
    <div v-if="$slots.actions" class="nameplate__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title?: string; eyebrow?: string }>();
</script>

<style scoped>
.nameplate {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  padding-bottom: 1rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--lens-graticule);
}
.nameplate__lead {
  min-width: 0;
}
.nameplate__eyebrow {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.22em;
  font-size: 0.6875rem;
  color: var(--lens-graph);
  margin-bottom: 0.625rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.nameplate__eyebrow::before {
  content: "";
  width: 0.5rem;
  height: 1px;
  background: var(--lens-primary);
}
.nameplate__title {
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(2rem, 1.4rem + 1.4vw, 2.625rem);
  line-height: 1.05;
  letter-spacing: -0.015em;
  margin: 0;
  color: var(--lens-ink);
  word-break: break-word;
}
.nameplate__lede {
  margin: 0.5rem 0 0;
  max-width: 52ch;
  color: var(--lens-ink-soft);
  font-size: 0.875rem;
  line-height: 1.5;
}
.nameplate__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
@media (max-width: 720px) {
  .nameplate {
    flex-direction: column;
  }
}
</style>
