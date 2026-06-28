<template>
  <aside class="sidebar" :class="{ 'sidebar--collapsed': !uiStore.sidebarVisible }">
    <div class="sidebar__brand">
      <span class="reticle" aria-hidden="true" />
      <span class="sidebar__wordmark">lens</span>
      <span class="sidebar__sub">watch console</span>
    </div>

    <nav class="sidebar__nav" aria-label="Primary">
      <button
        v-for="item in primary"
        :key="item.to"
        type="button"
        class="nav"
        :class="{ 'nav--active': isActive(item.to) }"
        @click="navigateTo(item.to)"
      >
        <i :class="item.icon" class="nav__icon" aria-hidden="true" />
        <span class="nav__label">{{ item.label }}</span>
      </button>

      <template v-if="admin.length">
        <div class="sidebar__section">Admin</div>
        <button
          v-for="item in admin"
          :key="item.to"
          type="button"
          class="nav"
          :class="{ 'nav--active': isActive(item.to) }"
          @click="navigateTo(item.to)"
        >
          <i :class="item.icon" class="nav__icon" aria-hidden="true" />
          <span class="nav__label">{{ item.label }}</span>
        </button>
      </template>
    </nav>

    <div class="sidebar__footer">
      <span class="sidebar__footer-dot" />
      <span class="sidebar__footer-mode">{{ isDark ? "night scope" : "day scope" }}</span>
      <span class="sidebar__footer-ver">v0.1</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
const uiStore = useUiStore();
const auth = useAuth();
const route = useRoute();
const { isDark } = useDarkMode();

const primary = [
  { to: "/", label: "Overview", icon: "pi pi-objects-column" },
  { to: "/domains", label: "Domains", icon: "pi pi-globe" },
  { to: "/urls", label: "URLs", icon: "pi pi-link" },
  { to: "/channels", label: "Channels", icon: "pi pi-bell" },
  { to: "/imports", label: "Import / Export", icon: "pi pi-arrow-exchange" },
];

const admin = computed(() =>
  auth.hasScope("admin")
    ? [
        { to: "/admin/settings", label: "Settings", icon: "pi pi-sliders-h" },
        { to: "/admin/dlq", label: "Dead-letter queue", icon: "pi pi-exclamation-triangle" },
        { to: "/admin/api-keys", label: "API keys", icon: "pi pi-key" },
      ]
    : [],
);

function isActive(to: string): boolean {
  if (to === "/") return route.path === "/";
  return route.path === to || route.path.startsWith(to + "/");
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--lens-panel);
  border-right: 1px solid var(--lens-graticule);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  min-height: calc(100vh - 41px);
}
.sidebar--collapsed {
  width: 56px;
}
.sidebar__brand {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 1rem 1.125rem;
  border-bottom: 1px solid var(--lens-graticule);
}
.sidebar__wordmark {
  font-family: var(--font-display);
  font-size: 1.625rem;
  line-height: 1;
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--lens-ink);
}
.sidebar__sub {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.5625rem;
  color: var(--lens-graph);
}
.sidebar--collapsed .sidebar__sub,
.sidebar--collapsed .nav__label,
.sidebar--collapsed .sidebar__section,
.sidebar--collapsed .sidebar__footer {
  display: none;
}
.sidebar--collapsed .nav {
  justify-content: center;
}
.sidebar--collapsed .sidebar__brand {
  justify-content: center;
  padding: 1rem 0;
}
.sidebar__nav {
  flex: 1;
  padding: 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.sidebar__section {
  margin: 0.875rem 1.125rem 0.375rem;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-size: 0.5625rem;
  color: var(--lens-graph);
  padding-bottom: 0.375rem;
  border-bottom: 1px solid var(--lens-graticule);
}
.nav {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1.125rem;
  background: transparent;
  border: 0;
  width: 100%;
  cursor: pointer;
  text-align: left;
  color: var(--lens-ink-soft);
  font: 500 0.875rem var(--font-sans);
  letter-spacing: 0.01em;
  position: relative;
}
.nav::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: transparent;
}
.nav:hover {
  color: var(--lens-ink);
  background: color-mix(in srgb, var(--lens-primary) 6%, transparent);
}
.nav--active {
  color: var(--lens-ink);
  background: color-mix(in srgb, var(--lens-primary) 10%, transparent);
}
.nav--active::before {
  background: var(--lens-primary);
  width: 2px;
}
.nav__icon {
  font-size: 0.8125rem;
  color: var(--lens-graph);
  width: 1.125rem;
  text-align: center;
}
.nav--active .nav__icon {
  color: var(--lens-primary);
}
.sidebar__footer {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 1.125rem;
  border-top: 1px solid var(--lens-graticule);
  font-family: var(--font-mono);
  font-size: 0.5625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--lens-graph);
}
.sidebar__footer-ver {
  margin-left: auto;
}
.sidebar__footer-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--lens-signal);
}
</style>
