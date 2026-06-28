<template>
  <div class="diff-viewer">
    <div class="diff-viewer__bar">
      <span class="diff-viewer__label">Unified diff</span>
      <span v-if="props.stats" class="diff-viewer__stats data-mono">
        <span class="added">+{{ props.stats.added }}</span>
        <span aria-hidden="true">/</span>
        <span class="removed">−{{ props.stats.removed }}</span>
      </span>
    </div>

    <div v-if="props.loading" class="diff-viewer__loading">
      <i class="pi pi-spin pi-circle-notch" /> <span class="data-mono">reading diff…</span>
    </div>

    <pre v-else-if="props.diffText" class="diff-viewer__content"><code>{{ props.diffText }}</code></pre>

    <p v-else class="diff-viewer__empty">No diff between the last two snapshots.</p>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    diffText?: string;
    stats?: { added: number; removed: number };
    loading?: boolean;
  }>(),
  {
    diffText: "",
    stats: () => ({ added: 0, removed: 0 }),
    loading: false,
  },
);
</script>

<style scoped>
.diff-viewer {
  border: 1px solid var(--lens-graticule);
  background: var(--lens-panel);
  border-radius: var(--lens-radius);
}
.diff-viewer__bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--lens-graticule);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.625rem;
  color: var(--lens-graph);
}
.diff-viewer__stats {
  font-size: 0.6875rem;
  letter-spacing: 0.04em;
  display: inline-flex;
  gap: 0.375rem;
}
.added { color: var(--lens-signal); }
.removed { color: var(--lens-alarm); }
.diff-viewer__loading,
.diff-viewer__empty {
  padding: 1.5rem;
  margin: 0;
  text-align: center;
  color: var(--lens-graph);
  font-size: 0.8125rem;
}
.diff-viewer__loading .data-mono {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  color: var(--lens-graph);
  margin-left: 0.375rem;
}
.diff-viewer__content {
  margin: 0;
  padding: 0.75rem 1rem;
  overflow-x: auto;
  max-height: 600px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.55;
  white-space: pre;
  color: var(--lens-ink-soft);
  tab-size: 2;
}
.diff-viewer__content code { font-family: inherit; }
</style>
