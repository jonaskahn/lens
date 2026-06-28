<template>
  <header class="topbar">
    <div class="topbar__lead">
      <Button
        icon="pi pi-bars"
        severity="secondary"
        text
        rounded
        aria-label="Toggle sidebar"
        @click="uiStore.toggleSidebar"
      />
      <span class="topbar__section eyebrow">{{ section }}</span>
    </div>

    <div class="topbar__spacer" />

    <div class="topbar__clock data-mono" aria-hidden="true">{{ clock }}</div>
    <ThemeToggle />
    <Button
      icon="pi pi-sign-out"
      severity="secondary"
      text
      rounded
      label="Sign out"
      class="topbar__signout"
      @click="auth.logout"
    />
  </header>
</template>

<script setup lang="ts">
const uiStore = useUiStore();
const auth = useAuth();
const route = useRoute();

const section = computed(() => {
  const p = route.path;
  if (p === "/") return "Overview";
  if (p.startsWith("/domains")) return "Domains";
  if (p.startsWith("/urls")) return "URLs";
  if (p.startsWith("/channels")) return "Channels";
  if (p.startsWith("/bindings")) return "Bindings";
  if (p.startsWith("/imports")) return "Import / Export";
  if (p.startsWith("/changes")) return "Changes";
  if (p.startsWith("/admin/api-keys")) return "Admin — API keys";
  if (p.startsWith("/admin/dlq")) return "Admin — Dead-letter queue";
  if (p.startsWith("/admin/settings")) return "Admin — Settings";
  return "lens";
});

const clock = ref("");
let timer: ReturnType<typeof setInterval> | null = null;
function tick() {
  clock.value = new Date().toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
onMounted(() => {
  tick();
  timer = setInterval(tick, 1000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 0.875rem;
  height: 41px;
  border-bottom: 1px solid var(--lens-graticule);
  background: color-mix(in srgb, var(--lens-panel) 88%, transparent);
  backdrop-filter: blur(6px);
  position: sticky;
  top: 0;
  z-index: 10;
}
.topbar__lead {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.topbar__section {
  color: var(--lens-graph);
}
.topbar__spacer {
  flex: 1;
}
.topbar__clock {
  font-size: 0.6875rem;
  letter-spacing: 0.08em;
  color: var(--lens-graph);
  font-variant-numeric: tabular-nums;
  padding-right: 0.5rem;
  margin-right: 0.25rem;
  border-right: 1px solid var(--lens-graticule);
}
.topbar__signout {
  color: var(--lens-ink-soft) !important;
}
@media (max-width: 760px) {
  .topbar__clock,
  .topbar__signout :deep(.p-button-label) {
    display: none;
  }
}
</style>
