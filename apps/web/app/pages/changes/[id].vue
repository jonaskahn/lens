<template>
  <div>
    <AppPageHeader title="Change">
      <template #eyebrow>
        <NuxtLink to="/urls" class="back-link">← URLs</NuxtLink>
      </template>
    </AppPageHeader>

    <Card v-if="change" class="mt-3">
      <template #content>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <div>
            <div class="text-sm text-surface-500">Added</div>
            <div class="text-lg font-bold">{{ change.added_count }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Removed</div>
            <div class="text-lg font-bold">{{ change.removed_count }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Semantic Score</div>
            <div class="text-lg font-bold">{{ (change.semantic_score as number)?.toFixed(3) ?? "-" }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Significant</div>
            <Tag :severity="change.significant ? 'warn' : 'info'">
              {{ change.significant ? "Yes" : "No" }}
            </Tag>
          </div>
        </div>
        <div class="text-sm text-surface-500">Detected at: {{ formatDate(change.created_at as string) }}</div>
      </template>
    </Card>

    <Card v-if="classification" class="mt-3 border-primary p-0">
      <template #title>
        <div class="flex items-center gap-2">
          <i class="pi pi-microchip-ai" />
          AI Classification
        </div>
      </template>
      <template #content>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div class="text-sm text-surface-500">Change Type</div>
            <Tag severity="info" :value="classification.change_type" />
          </div>
          <div>
            <div class="text-sm text-surface-500">Meaningful</div>
            <Tag :severity="classification.is_meaningful ? 'success' : 'warn'">
              {{ classification.is_meaningful ? "Yes" : "No" }}
            </Tag>
          </div>
          <div>
            <div class="text-sm text-surface-500">Severity</div>
            <div class="text-lg font-bold">{{ classification.severity }}/5</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Confidence</div>
            <div class="text-lg font-bold">{{ ((classification.confidence as number ?? 0) * 100).toFixed(0) }}%</div>
          </div>
        </div>

        <div v-if="classification.summary" class="mt-3">
          <div class="text-sm text-surface-500 mb-1">Summary</div>
          <p class="text-sm">{{ classification.summary }}</p>
        </div>

        <div v-if="Object.keys(classification.extracted_fields as Record<string, unknown>).length" class="mt-3">
          <div class="text-sm text-surface-500 mb-1">Extracted Fields</div>
          <div class="flex flex-wrap gap-2">
            <Tag
              v-for="(value, key) in (classification.extracted_fields as Record<string, unknown>)"
              :key="String(key)"
              severity="info"
              rounded
            >
              {{ key }}: {{ value }}
            </Tag>
          </div>
        </div>

        <div class="mt-2 text-xs text-surface-400">
          Model: {{ classification.model_id ?? "unknown" }}
        </div>
      </template>
    </Card>

    <Card class="mt-3">
      <template #title>Diff</template>
      <template #content>
        <DiffViewer :diff-text="diffContent" :loading="diffLoading" :stats="diffStats" />
        <div v-if="diffError" class="mt-2">
          <Message severity="error">{{ diffError }}</Message>
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "read",
});

const route = useRoute();
const api = useApi();
const toast = useToast();

const change = ref<Record<string, unknown> | null>(null);
const classification = ref<Record<string, unknown> | null>(null);
const diffContent = ref("");
const diffLoading = ref(false);
const diffError = ref("");

const diffStats = computed(() => ({
  added: (change.value?.added_count as number) ?? 0,
  removed: (change.value?.removed_count as number) ?? 0,
}));

function formatDate(iso?: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

async function loadChange() {
  try {
    change.value = await api.get(`/api/v1/changes/${route.params.id}`);
  } catch (err) {
    handleApiError(err, toast);
  }
}

async function loadClassification() {
  try {
    classification.value = await api.get(`/api/v1/changes/${route.params.id}/classification`);
  } catch {
    // classification is optional - silently ignore if not available
  }
}

async function loadDiff() {
  diffLoading.value = true;
  diffError.value = "";
  try {
    diffContent.value = await api.get<string>(`/api/v1/changes/${route.params.id}/diff`);
  } catch (err) {
    diffError.value = (err as Error).message ?? "Failed to load diff";
  } finally {
    diffLoading.value = false;
  }
}

onMounted(() => {
  loadChange();
  loadClassification();
  loadDiff();
});
</script>

<style scoped>
.back-link {
  color: var(--lens-primary);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.6875rem;
  text-decoration: none;
}
.back-link:hover { text-decoration: underline; text-underline-offset: 2px; }
.border-primary {
  border-left: 2px solid var(--lens-primary);
}
</style>
