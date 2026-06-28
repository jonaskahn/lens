<template>
  <div>
    <AppPageHeader :title="(url?.address as string) ?? 'URL'">
      <template #eyebrow>
        <NuxtLink to="/urls" class="back-link">← URLs</NuxtLink>
      </template>
      <template #actions>
        <Button
          v-if="auth.hasScope('write')"
          label="Enqueue crawl now"
          icon="pi pi-play"
          :loading="checking"
          @click="checkNow"
        />
        <Button
          v-if="auth.hasScope('write')"
          icon="pi pi-pencil"
          severity="secondary"
          label="Edit"
          @click="showEdit = true"
        />
      </template>
    </AppPageHeader>

    <Card v-if="url" class="mt-3">
      <template #content>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div class="text-sm text-surface-500">Status</div>
            <Tag :severity="statusSeverity(url.status as string)" :value="url.status" />
          </div>
          <div>
            <div class="text-sm text-surface-500">Interval</div>
            <div>{{ url.interval_seconds }}s</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Last Checked</div>
            <div>{{ formatDate(url.last_checked_at as string) }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Next Due</div>
            <div>{{ formatDate(url.next_due_at as string) }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Last Hash</div>
            <div class="text-xs font-mono truncate max-w-12rem">{{ (url.last_hash as string)?.slice(0, 16) ?? "-" }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Consecutive Errors</div>
            <div>{{ url.consecutive_errors ?? 0 }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Domain</div>
            <div>{{ url.domain_id }}</div>
          </div>
          <div>
            <div class="text-sm text-surface-500">Enabled</div>
            <Tag :severity="url.enabled ? 'success' : 'secondary'">{{ url.enabled ? "Yes" : "No" }}</Tag>
          </div>
        </div>
      </template>
    </Card>

    <TabView class="mt-3">
      <TabPanel header="Changes" value="0">
        <div class="flex gap-3 mb-3 flex-wrap">
          <IftaLabel>
            <DatePicker v-model="filterSince" show-time placeholder="Since" class="w-13rem" />
            <label>Since</label>
          </IftaLabel>
          <IftaLabel>
            <DatePicker v-model="filterUntil" show-time placeholder="Until" class="w-13rem" />
            <label>Until</label>
          </IftaLabel>
          <Button icon="pi pi-filter" label="Apply" @click="loadChanges" />
        </div>

        <DataTable :value="changes" :loading="changeLoading" paginator :rows="10" striped-rows>
          <Column header="Significant">
            <template #body="{ data }">
              <Tag :severity="data.significant ? 'warn' : 'info'">
                {{ data.significant ? "Yes" : "No" }}
              </Tag>
            </template>
          </Column>
          <Column field="added_count" header="Added" />
          <Column field="removed_count" header="Removed" />
          <Column field="semantic_score" header="Semantic Score">
            <template #body="{ data }">
              {{ (data.semantic_score as number)?.toFixed(3) ?? "-" }}
            </template>
          </Column>
          <Column field="created_at" header="Detected At">
            <template #body="{ data }">
              {{ formatDate(data.created_at as string) }}
            </template>
          </Column>
          <Column header="Actions">
            <template #body="{ data }">
              <Button
                icon="pi pi-eye"
                severity="secondary"
                text
                rounded
                aria-label="View change"
                @click="navigateTo(`/changes/${data.id}`)"
              />
            </template>
          </Column>
        </DataTable>
      </TabPanel>

      <TabPanel header="Snapshots" value="1">
        <DataTable :value="snapshots" :loading="snapLoading" paginator :rows="10" striped-rows>
          <Column field="http_status" header="HTTP Status" />
          <Column field="byte_size" header="Size" />
          <Column field="fetched_at" header="Fetched At">
            <template #body="{ data }">
              {{ formatDate(data.fetched_at as string) }}
            </template>
          </Column>
          <Column header="Actions">
            <template #body="{ data }">
              <Button
                icon="pi pi-eye"
                severity="secondary"
                text
                rounded
                aria-label="View snapshot"
                @click="viewSnapshot(data)"
              />
            </template>
          </Column>
        </DataTable>
      </TabPanel>
    </TabView>

    <Dialog
      v-model:visible="showEdit"
      header="Edit URL"
      :modal="true"
      class="w-full max-w-xl"
    >
      <div class="flex flex-col gap-3">
        <div>
          <label class="block mb-1">Address</label>
          <InputText v-model="editForm.address" class="w-full" />
        </div>
        <div>
          <label class="block mb-1">Interval (seconds)</label>
          <InputNumber v-model="editForm.interval_seconds" class="w-full" :min="300" />
        </div>
        <div class="flex items-center gap-2">
          <ToggleSwitch v-model="editForm.enabled" input-id="edit-enabled" />
          <label for="edit-enabled">Enabled</label>
        </div>
        <JsonField v-model="editForm.crawl_config" label="Crawl Config" />
        <JsonField v-model="editForm.diff_config" label="Diff Config" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showEdit = false" />
        <Button label="Save" :loading="saving" @click="saveEdit" />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="showSnapshotContent"
      header="Snapshot Content"
      :modal="true"
      class="w-full max-w-4xl"
      :style="{ width: '90vw' }"
    >
      <pre v-if="snapshotContent" class="snapshot-text">{{ snapshotContent }}</pre>
      <p v-else class="text-surface-500">Loading...</p>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "read",
});

const route = useRoute();
const api = useApi();
const auth = useAuth();
const toast = useToast();

const url = ref<Record<string, unknown> | null>(null);
const changes = ref<Array<Record<string, unknown>>>([]);
const snapshots = ref<Array<Record<string, unknown>>>([]);
const changeLoading = ref(false);
const snapLoading = ref(false);
const checking = ref(false);
const showEdit = ref(false);
const saving = ref(false);
const showSnapshotContent = ref(false);
const snapshotContent = ref("");

const filterSince = ref<Date | null>(null);
const filterUntil = ref<Date | null>(null);

const editForm = reactive({
  address: "",
  interval_seconds: 3600,
  enabled: true,
  crawl_config: null as Record<string, unknown> | null,
  diff_config: null as Record<string, unknown> | null,
});

function statusSeverity(status: string): "success" | "info" | "warn" | "danger" | "secondary" {
  const map: Record<string, "success" | "info" | "warn" | "danger" | "secondary"> = {
    Idle: "success", Crawling: "info", Enqueued: "warn", Error: "danger", Disabled: "secondary",
  };
  return map[status] ?? "secondary";
}

function formatDate(iso?: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

async function loadUrl() {
  try {
    url.value = await api.get(`/api/v1/urls/${route.params.id}`);
  } catch (err) {
    handleApiError(err, toast);
  }
}

async function loadChanges() {
  changeLoading.value = true;
  try {
    const params: Record<string, unknown> = { limit: 50 };
    if (filterSince.value) params.since = filterSince.value.toISOString();
    if (filterUntil.value) params.until = filterUntil.value.toISOString();
    const res = await api.get<{ items: Array<Record<string, unknown>> }>(
      `/api/v1/urls/${route.params.id}/changes`,
      { query: params },
    );
    changes.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    changeLoading.value = false;
  }
}

async function loadSnapshots() {
  snapLoading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>(
      `/api/v1/urls/${route.params.id}/snapshots`,
      { query: { limit: 20 } },
    );
    snapshots.value = res.items ?? [];
  } catch {
    // silently ignore
  } finally {
    snapLoading.value = false;
  }
}

async function checkNow() {
  checking.value = true;
  try {
    const res = await api.post<{ enqueued: number }>(`/api/v1/urls/${route.params.id}/check`);
    toast.add({
      severity: "success",
      summary: "Check Enqueued",
      detail: `${res.enqueued ?? 0} URL(s) enqueued`,
      life: 3000,
    });
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    checking.value = false;
  }
}

async function saveEdit() {
  saving.value = true;
  try {
    const body: Record<string, unknown> = {
      address: editForm.address,
      interval_seconds: editForm.interval_seconds,
      enabled: editForm.enabled,
    };
    if (editForm.crawl_config) body.crawl_config = editForm.crawl_config;
    if (editForm.diff_config) body.diff_config = editForm.diff_config;

    await api.patch(`/api/v1/urls/${route.params.id}`, { body });
    toast.add({ severity: "success", summary: "URL updated", life: 3000 });
    showEdit.value = false;
    await loadUrl();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    saving.value = false;
  }
}

async function viewSnapshot(data: Record<string, unknown>) {
  showSnapshotContent.value = true;
  snapshotContent.value = "";
  try {
    const text = await api.get<string>(`/api/v1/snapshots/${data.id}/content`);
    snapshotContent.value = text ?? "";
  } catch (err) {
    handleApiError(err, toast);
  }
}

watch(() => url.value, (val) => {
  if (val) {
    editForm.address = val.address as string;
    editForm.interval_seconds = (val.interval_seconds as number) ?? 3600;
    editForm.enabled = (val.enabled as boolean) ?? true;
    editForm.crawl_config = (val.crawl_config as Record<string, unknown>) ?? null;
    editForm.diff_config = (val.diff_config as Record<string, unknown>) ?? null;
  }
});

onMounted(() => {
  loadUrl();
  loadChanges();
  loadSnapshots();
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
.snapshot-text {
  background: var(--lens-panel);
  border: 1px solid var(--lens-graticule);
  padding: 1rem;
  border-radius: var(--lens-radius);
  max-height: 500px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
