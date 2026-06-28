<template>
  <div>
    <AppPageHeader
      title="Overview"
      eyebrow="operator station"
    >
      The state of every tracked page at one glance: one tick per URL, placed by when it is next due and colored by status.
    </AppPageHeader>

    <!-- Stat dials -->
    <section class="dials">
      <div v-for="widget in widgets" :key="widget.id" class="dial" :data-alarm="widget.alarm && widget.value > 0 ? '' : null">
        <span class="dial__label">{{ widget.label }}</span>
        <span class="dial__value">{{ formatNum(widget.value) }}</span>
        <span class="dial__hint data-mono">{{ widget.hint }}</span>
      </div>
    </section>

    <!-- Aperture bar — the signature element -->
    <section class="aperture-block">
      <div class="aperture-block__head">
        <div class="eyebrow">Aperture · next due across all URLs</div>
        <ul class="aperture__legend" aria-label="Status colors">
          <li><i style="background: var(--lens-graph)" />Idle</li>
          <li><i style="background: var(--lens-primary)" />Crawling</li>
          <li><i style="background: var(--lens-secondary)" />Enqueued</li>
          <li><i style="background: var(--lens-alarm)" />Error / overdue</li>
          <li><i style="background: var(--lens-graph); opacity: 0.35" />Disabled</li>
        </ul>
      </div>

      <div class="aperture">
        <div
v-if="nowPos != null && nowPos >= 0 && nowPos <= 100" class="aperture__now"
          :style="{ left: nowPos + '%' }" aria-hidden="true">
          <span class="aperture__now-label data-mono">NOW</span>
        </div>

        <div v-if="allUrls.length" class="aperture__rail">
          <span
            v-for="(tick, idx) in ticks"
            :key="idx"
            class="aperture__tick"
            :data-state="tick.state"
            :style="{ left: tick.pct + '%', top: tick.top + '%', bottom: tick.bottom + '%' }"
            :title="`${tick.address}\n${tick.state}\ndue ${tick.dueLabel}`"
          />
        </div>

        <div v-else class="aperture__empty" :class="{ 'aperture__empty--loading': loading }">
          <span class="reticle" aria-hidden="true" />
          <p>
            <template v-if="loading">Loading the watchlist…</template>
            <template v-else>No pages tracked yet. Add a <NuxtLink to="/domains">domain</NuxtLink> and a <NuxtLink to="/urls">URL</NuxtLink> to start watching.</template>
          </p>
        </div>

        <div v-if="allUrls.length && axisMax > axisMin" class="aperture__axis">
          <span>{{ axisLabel(axisMin) }}</span>
          <span>{{ axisLabel(mid) }}</span>
          <span>{{ axisLabel(axisMax) }}</span>
        </div>
      </div>
    </section>

    <!-- Two panels -->
    <section class="grid">
      <div class="panel aperture-panel">
        <header class="panel__head">
          <h2 class="panel__title">Status mix</h2>
          <span class="data-mono panel__count">{{ allUrls.length }} tracked</span>
        </header>
        <div class="panel__body">
          <Chart v-if="allUrls.length" type="doughnut" :data="statusChartData" :options="doughnutOptions" class="chart" />
          <div v-else class="placeholder">
            <p>Nothing to chart yet.</p>
          </div>
        </div>
      </div>

      <div class="panel aperture-panel">
        <header class="panel__head">
          <h2 class="panel__title">Most recent changes</h2>
          <NuxtLink v-if="recentChanges.length" to="/urls" class="panel__link">Open URLs →</NuxtLink>
        </header>
        <div class="panel__body panel__body--flush">
          <DataTable v-if="recentChanges.length" :value="recentChanges" :loading="loading" size="small" :rows="6">
            <Column field="url_id" header="URL">
              <template #body="{ data }">
                <code class="data-mono">{{ String(data.url_id ?? "").slice(0, 8) || "—" }}</code>
              </template>
            </Column>
            <Column field="added_count" header="Added">
              <template #body="{ data }">
                <span class="added">+{{ data.added_count ?? 0 }}</span>
              </template>
            </Column>
            <Column field="removed_count" header="Removed">
              <template #body="{ data }">
                <span class="removed">−{{ data.removed_count ?? 0 }}</span>
              </template>
            </Column>
            <Column field="significant" header="Significant">
              <template #body="{ data }">
                <Tag :severity="data.significant ? 'warn' : 'secondary'" :value="data.significant ? 'yes' : 'no'" />
              </template>
            </Column>
          </DataTable>
          <div v-else class="placeholder placeholder--tall">
            <p>No changes seen yet. They will appear here the first time a crawl detects a diff.</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "read",
});

const api = useApi();

// tick shape used by the aperture bar
interface ApertureTick {
  address: string;
  state: string;
  pct: number;
  top: string;
  bottom: string;
  dueLabel: string;
}

const allUrls = ref<Array<Record<string, unknown>>>([]);
const recentChanges = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);

const widgets = reactive([
  { id: "domains", label: "Domains", value: 0, hint: "tracked hosts", alarm: false },
  { id: "urls", label: "URLs", value: 0, hint: "watched pages", alarm: false },
  { id: "due", label: "Due now", value: 0, hint: "next_due ≤ now", alarm: true },
  { id: "errors", label: "Errors", value: 0, hint: "consecutive failures", alarm: true },
]);

const statusChartData = ref({
  labels: ["Idle", "Crawling", "Enqueued", "Error", "Disabled"],
  datasets: [{ data: [0, 0, 0, 0, 0], backgroundColor: ["oklch(58% 0.006 285.885)", "oklch(55% 0.115 274.713)", "oklch(70% 0.128 66.29)", "oklch(54% 0.246 16.439)", "oklch(86% 0.005 286.32)"], borderColor: "transparent", borderWidth: 0 }],
});

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: "62%",
  plugins: {
    legend: { position: "bottom" as const, labels: { boxWidth: 8, boxHeight: 8, font: { family: "IBM Plex Mono", size: 11 } } },
  },
};

const axisMin = ref(0);
const axisMax = ref(1);

const mid = computed(() => (axisMin.value + axisMax.value) / 2);

// Derived time extent for the aperture axis — computed; decl side-effects go via watchEffect.
const extent = computed(() => {
  const now = Date.now();
  let lo = Number.POSITIVE_INFINITY;
  let hi = Number.NEGATIVE_INFINITY;
  for (const u of allUrls.value) {
    const due = u.next_due_at as string | undefined;
    if (!due) continue;
    const t = new Date(due).getTime();
    if (Number.isFinite(t)) {
      lo = Math.min(lo, t);
      hi = Math.max(hi, t);
    }
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
    lo = now - 6 * 3600_000;
    hi = now + 18 * 3600_000;
  }
  const pad = (hi - lo) * 0.04 || 3600_000;
  return { lo: lo - pad, hi: hi + pad };
});

watchEffect(() => {
  axisMin.value = extent.value.lo;
  axisMax.value = extent.value.hi;
});

const ticks = computed<ApertureTick[]>(() => {
  const now = Date.now();
  const { lo, hi } = extent.value;
  const span = hi - lo || 1;

  return allUrls.value.map((u) => {
    const status = (u.status as string) ?? "Disabled";
    const due = u.next_due_at as string | undefined;
    const dueMs = due ? new Date(due).getTime() : null;
    let pct: number;
    if (dueMs == null || !Number.isFinite(dueMs)) pct = 100;
    else pct = ((dueMs - lo) / span) * 100;
    pct = Math.max(0, Math.min(100, pct));

    const overdue = dueMs != null && dueMs <= now && status !== "Error" && status !== "Disabled";
    return {
      address: (u.address as string) ?? "(unnamed)",
      state: overdue ? "Error" : dueMs == null ? "Disabled" : status,
      pct,
      top: overdue ? "10%" : "22%",
      bottom: overdue ? "10%" : "22%",
      dueLabel: due ? new Date(due).toLocaleString() : "—",
    };
  });
});

const nowPos = computed(() => {
  if (!allUrls.value.length) return null;
  const now = Date.now();
  const span = axisMax.value - axisMin.value || 1;
  return ((now - axisMin.value) / span) * 100;
});

function axisLabel(ts: number): string {
  if (!Number.isFinite(ts)) return "—";
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatNum(n: number): string {
  return n.toLocaleString();
}

async function loadDashboard() {
  loading.value = true;
  try {
    const [domRes, urlRes] = await Promise.all([
      api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/domains", { query: { limit: 1 } }),
      api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/urls", { query: { limit: 200 } }),
    ]);

    const urls = urlRes.items ?? [];
    // /domains returns a paginated list; total count is usually carried in a metadata field.
    // Fall back to a follow-up count request only if needed — keep it cheap by trusting items length.
    const domCount = (domRes as Record<string, unknown>).total as number | undefined;
    widgets[0]!.value = domCount != null ? domCount : ((domRes as { items?: unknown[] }).items?.length ?? 0);
    widgets[1]!.value = urls.length;
    allUrls.value = urls;

    const now = Date.now();
    widgets[2]!.value = urls.filter((u) => {
      const due = u.next_due_at as string;
      return due && new Date(due).getTime() <= now;
    }).length;
    widgets[3]!.value = urls.filter((u) => u.status === "Error").length;

    const statusCounts: Record<string, number> = { Idle: 0, Crawling: 0, Enqueued: 0, Error: 0, Disabled: 0 };
    for (const u of urls) {
      const s = (u.status as string) ?? "Disabled";
      statusCounts[s] = (statusCounts[s] ?? 0) + 1;
    }
    statusChartData.value = {
      labels: ["Idle", "Crawling", "Enqueued", "Error", "Disabled"],
      datasets: [{
        data: [
          statusCounts.Idle ?? 0,
          statusCounts.Crawling ?? 0,
          statusCounts.Enqueued ?? 0,
          statusCounts.Error ?? 0,
          statusCounts.Disabled ?? 0,
        ],
        backgroundColor: ["oklch(58% 0.006 285.885)", "oklch(55% 0.115 274.713)", "oklch(70% 0.128 66.29)", "oklch(54% 0.246 16.439)", "oklch(86% 0.005 286.32)"],
        borderColor: "transparent",
        borderWidth: 0,
      }],
    };
  } catch {
    // keep empty state visible; toast would be noise here
  } finally {
    loading.value = false;
  }
}

async function loadRecentChanges() {
  recentChanges.value = [];
}

onMounted(() => {
  loadDashboard();
  loadRecentChanges();
});
</script>

<style scoped>
.dials {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--lens-graticule);
  border: 1px solid var(--lens-graticule);
  margin-bottom: 1.5rem;
}
.dial {
  background: var(--lens-panel);
  border: 0;
  padding: 1rem 1.125rem 1.125rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.dial__label {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.625rem;
  color: var(--lens-graph);
}
.dial__value {
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(2rem, 1.5rem + 1vw, 2.75rem);
  line-height: 1;
  color: var(--lens-ink);
  font-variant-numeric: tabular-nums;
}
.dial[data-alarm] .dial__value {
  color: var(--lens-alarm);
}
.dial__hint {
  font-size: 0.625rem;
  color: var(--lens-graph);
  letter-spacing: 0.05em;
}
@media (max-width: 900px) {
  .dials { grid-template-columns: repeat(2, 1fr); }
}

.aperture-block {
  margin-bottom: 2.5rem;
}
.aperture-block__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 1rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}
.aperture {
  position: relative;
  height: 5.5rem;
  border: 1px solid var(--lens-graticule);
  background: var(--lens-panel);
}
.aperture::before,
.aperture::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: var(--lens-graticule);
  opacity: 0.6;
}
.aperture::before { top: 0; }
.aperture::after { bottom: 0; }
.aperture__rail {
  position: absolute;
  inset: 0;
}
.aperture__tick {
  position: absolute;
  width: 1px;
  background: var(--lens-graph);
  transform: scaleX(1);
  transition: transform 0.2s ease;
}
.aperture__tick:hover { transform: scaleX(2.5); }
.aperture__tick[data-state="Crawling"] { background: var(--lens-primary); }
.aperture__tick[data-state="Enqueued"] { background: var(--lens-secondary); }
.aperture__tick[data-state="Error"]    { background: var(--lens-alarm); }
.aperture__tick[data-state="Disabled"] { background: var(--lens-graph); opacity: 0.35; }
.aperture__now {
  position: absolute;
  top: -0.5rem;
  bottom: -0.5rem;
  width: 0;
  border-left: 1px dashed var(--lens-primary);
  pointer-events: none;
}
.aperture__now-label {
  position: absolute;
  top: -1rem;
  left: 0;
  transform: translateX(-50%);
  font-size: 0.5625rem;
  letter-spacing: 0.16em;
  color: var(--lens-primary);
}
.aperture__axis {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1.4rem;
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 0.5625rem;
  letter-spacing: 0.08em;
  color: var(--lens-graph);
}
.aperture__empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: center;
  justify-content: center;
  color: var(--lens-graph);
  text-align: center;
  font-size: 0.8125rem;
}
.aperture__empty p { margin: 0; max-width: 28ch; }
.aperture__empty a {
  color: var(--lens-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.aperture__legend {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  color: var(--lens-graph);
}
.aperture__legend li {
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}
.aperture-panel {
  display: flex;
  flex-direction: column;
}
.panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  padding: 1rem 1.125rem 0.75rem;
  border-bottom: 1px solid var(--lens-graticule);
}
.panel__title {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.6875rem;
  color: var(--lens-graph);
  margin: 0;
}
.panel__count {
  font-size: 0.625rem;
  color: var(--lens-graph);
  letter-spacing: 0.08em;
}
.panel__link {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--lens-primary);
  text-decoration: none;
}
.panel__body {
  padding: 1rem 1.125rem;
  flex: 1;
  min-height: 16rem;
}
.panel__body--flush {
  padding: 0;
}
.chart {
  height: 16rem !important;
}
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 16rem;
  color: var(--lens-graph);
  font-size: 0.8125rem;
  padding: 0 2rem;
  text-align: center;
}
.placeholder--tall {
  height: 100%;
  min-height: 16rem;
}
.placeholder p { margin: 0; max-width: 32ch; }
.added { color: var(--lens-signal); font-variant-numeric: tabular-nums; }
.removed { color: var(--lens-alarm); font-variant-numeric: tabular-nums; }
</style>
