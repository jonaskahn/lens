<template>
  <div>
    <AppPageHeader eyebrow="Watched pages" title="URLs">
      Each row is one URL lens will crawl on its interval, diff against the last snapshot, and route to channels.
      <template #actions>
        <Button
          v-if="auth.hasScope('write')"
          label="Add URL"
          icon="pi pi-plus"
          @click="showCreate = true"
        />
      </template>
    </AppPageHeader>

    <div class="filter-bar mt-3">
      <div class="filter-field">
        <label for="url-filter-domain">Domain</label>
        <Select
          v-model="filterDomainId"
          input-id="url-filter-domain"
          :options="domainOptions"
          option-label="label"
          option-value="value"
          placeholder="All domains"
          show-clear
          class="w-full"
        />
      </div>
      <div class="filter-field">
        <label for="url-filter-status">Status</label>
        <Select
          v-model="filterStatus"
          input-id="url-filter-status"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          placeholder="All statuses"
          show-clear
          class="w-full"
        />
      </div>
      <div class="filter-field">
        <label for="url-filter-search">Search</label>
        <InputText id="url-filter-search" v-model="searchQuery" placeholder="Search..." class="w-full" />
      </div>
      <Button icon="pi pi-search" label="Search" @click="loadUrls" />
    </div>

    <DataTable :value="urls" :loading="loading" paginator :rows="20" striped-rows class="mt-3">
      <Column field="address" header="Address" sortable />
      <Column field="status" header="Status">
        <template #body="{ data }">
          <Tag :severity="statusSeverity(data.status as string)">
            {{ data.status }}
          </Tag>
        </template>
      </Column>
      <Column field="interval_seconds" header="Interval (s)" />
      <Column field="next_due_at" header="Next Due">
        <template #body="{ data }">
          {{ formatDate(data.next_due_at as string) }}
        </template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <Button icon="pi pi-pencil" severity="secondary" text rounded aria-label="Edit" @click="editUrl(data)" />
          <Button icon="pi pi-trash" severity="danger" text rounded aria-label="Delete" @click="confirmDelete(data)" />
        </template>
      </Column>
    </DataTable>

    <Dialog
      v-model:visible="showCreate"
      :header="editingId ? 'Edit URL' : 'Add URL'"
      :modal="true"
      class="w-full max-w-xl"
    >
      <div class="flex flex-col gap-3">
        <div>
          <label class="block mb-1">Domain</label>
          <Select
            v-model="form.domain_id"
            :options="domainOptions"
            option-label="label"
            option-value="value"
            class="w-full"
            :disabled="!!editingId"
            placeholder="Select domain"
          />
        </div>
        <div>
          <label class="block mb-1">Address (URL)</label>
          <InputText v-model="form.address" class="w-full" placeholder="https://..." />
        </div>
        <div>
          <label class="block mb-1">Interval (seconds)</label>
          <InputNumber v-model="form.interval_seconds" class="w-full" :min="300" />
        </div>
        <div class="flex items-center gap-2">
          <ToggleSwitch v-model="form.enabled" input-id="url-enabled" />
          <label for="url-enabled">Enabled</label>
        </div>
        <JsonField v-model="form.crawl_config" label="Crawl Config" />
        <JsonField v-model="form.diff_config" label="Diff Config" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showCreate = false" />
        <Button label="Save" :loading="saving" @click="saveUrl" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "read",
});

const api = useApi();
const auth = useAuth();
const toast = useToast();
const confirm = useConfirm();

const urls = ref<Array<Record<string, unknown>>>([]);
const domains = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const editingId = ref<string | null>(null);

const filterDomainId = ref<string | null>(null);
const filterStatus = ref<string | null>(null);
const searchQuery = ref("");

const domainOptions = computed(() =>
  domains.value.map((d) => ({ label: d.host as string, value: d.id as string })),
);

const statusOptions = [
  { label: "Idle", value: "Idle" },
  { label: "Crawling", value: "Crawling" },
  { label: "Enqueued", value: "Enqueued" },
  { label: "Error", value: "Error" },
  { label: "Disabled", value: "Disabled" },
];

const form = reactive({
  domain_id: "",
  address: "",
  interval_seconds: 3600,
  enabled: true,
  crawl_config: null as Record<string, unknown> | null,
  diff_config: null as Record<string, unknown> | null,
});

function statusSeverity(status: string): "success" | "info" | "warn" | "danger" | "secondary" {
  const map: Record<string, "success" | "info" | "warn" | "danger" | "secondary"> = {
    Idle: "success",
    Crawling: "info",
    Enqueued: "warn",
    Error: "danger",
    Disabled: "secondary",
  };
  return map[status] ?? "secondary";
}

function formatDate(iso?: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

async function loadUrls() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = { limit: 200 };
    if (filterDomainId.value) params.domain_id = filterDomainId.value;
    if (filterStatus.value) params.status = filterStatus.value;
    if (searchQuery.value) params.q = searchQuery.value;

    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/urls", {
      query: params,
    });
    urls.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

async function loadDomains() {
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/domains", {
      query: { limit: 200 },
    });
    domains.value = res.items ?? [];
  } catch {
    // silently ignore domains load errors
  }
}

function editUrl(data: Record<string, unknown>) {
  editingId.value = data.id as string;
  form.domain_id = data.domain_id as string;
  form.address = data.address as string;
  form.interval_seconds = (data.interval_seconds as number) ?? 3600;
  form.enabled = (data.enabled as boolean) ?? true;
  form.crawl_config = (data.crawl_config as Record<string, unknown>) ?? null;
  form.diff_config = (data.diff_config as Record<string, unknown>) ?? null;
  showCreate.value = true;
}

async function saveUrl() {
  saving.value = true;
  try {
    const body: Record<string, unknown> = {
      address: form.address,
      interval_seconds: form.interval_seconds,
      enabled: form.enabled,
    };
    if (form.crawl_config) body.crawl_config = form.crawl_config;
    if (form.diff_config) body.diff_config = form.diff_config;

    if (editingId.value) {
      await api.patch(`/api/v1/urls/${editingId.value}`, { body });
      toast.add({ severity: "success", summary: "URL updated", life: 3000 });
    } else {
      body.domain_id = form.domain_id;
      await api.post("/api/v1/urls", { body });
      toast.add({ severity: "success", summary: "URL created", life: 3000 });
    }

    showCreate.value = false;
    resetForm();
    await loadUrls();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    saving.value = false;
  }
}

function confirmDelete(data: Record<string, unknown>) {
  confirm.require({
    message: `Delete URL "${data.address}"?`,
    header: "Confirm Deletion",
    icon: "pi pi-exclamation-triangle",
    accept: async () => {
      try {
        await api.del(`/api/v1/urls/${data.id as string}`);
        toast.add({ severity: "success", summary: "URL deleted", life: 3000 });
        await loadUrls();
      } catch (err) {
        handleApiError(err, toast);
      }
    },
  });
}

function resetForm() {
  editingId.value = null;
  form.domain_id = "";
  form.address = "";
  form.interval_seconds = 3600;
  form.enabled = true;
  form.crawl_config = null;
  form.diff_config = null;
}

onMounted(() => {
  loadDomains();
  loadUrls();
});
</script>

<style scoped>
.filter-bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(11rem, 1fr)) auto;
  gap: 0.75rem;
  align-items: end;
}

.filter-bar :deep(.p-select),
.filter-bar :deep(.p-inputtext) {
  width: 100%;
}

.filter-field {
  display: grid;
  gap: 0.375rem;
}

.filter-field label {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

@media (max-width: 860px) {
  .filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .filter-bar {
    grid-template-columns: 1fr;
  }

  .filter-bar :deep(.p-button) {
    width: 100%;
  }
}
</style>
