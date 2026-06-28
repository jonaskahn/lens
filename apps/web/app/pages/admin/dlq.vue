<template>
  <div>
    <AppPageHeader eyebrow="Admin · failed deliveries" title="Dead-letter queue">
      Messages that exhausted their retries waiting here for replay or discard.
    </AppPageHeader>

    <div class="dlq-toolbar">
      <div class="dlq-field">
        <label for="dlq-queue">Event</label>
        <Select
          v-model="selectedQueue"
          input-id="dlq-queue"
          :options="queueOptions"
          option-label="label"
          option-value="value"
          class="w-full"
          placeholder="Queue filter"
        />
      </div>
      <Button icon="pi pi-refresh" aria-label="Reload" :loading="loading" class="dlq-reload" @click="loadMessages" />
    </div>

    <DataTable :value="messages" :loading="loading" striped-rows class="mb-3">
      <Column field="message_id" header="Message ID">
        <template #body="{ data }">
          <code class="text-xs">{{ (data.message_id as string)?.slice(0, 12) }}</code>
        </template>
      </Column>
      <Column field="queue" header="Queue" />
      <Column field="error" header="Error" />
      <Column field="attempts" header="Attempts" />
      <Column field="last_attempt_at" header="Last Attempt">
        <template #body="{ data }">
          {{ formatDate(data.last_attempt_at as string) }}
        </template>
      </Column>
    </DataTable>

    <div class="flex gap-2">
      <Button
        label="Replay All"
        icon="pi pi-replay"
        severity="warn"
        :loading="replaying"
        :disabled="messages.length === 0"
        @click="replayAll"
      />
      <Button
        label="Discard All"
        icon="pi pi-trash"
        severity="danger"
        :loading="discarding"
        :disabled="messages.length === 0"
        @click="discardAll"
      />
    </div>

    <Divider />

    <Card class="mt-3">
      <template #title>Retention</template>
      <template #content>
        <Button
          label="Run Retention"
          icon="pi pi-broom"
          :loading="retentionRunning"
          @click="runRetention"
        />
        <div v-if="retentionResult" class="mt-3">
          <Message severity="success">
            <div>Snapshots evicted: {{ (retentionResult as Record<string, unknown>).snapshots_evicted }}</div>
            <div>Blobs deleted: {{ (retentionResult as Record<string, unknown>).blobs_deleted }}</div>
            <div>Orphan blobs deleted: {{ (retentionResult as Record<string, unknown>).orphan_blobs_deleted }}</div>
          </Message>
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "admin",
});

const api = useApi();
const toast = useToast();

const messages = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const replaying = ref(false);
const discarding = ref(false);
const retentionRunning = ref(false);
const retentionResult = ref<unknown>(null);

const selectedQueue = ref("events");

const queueOptions = [
  { label: "Events", value: "events" },
  { label: "Crawl", value: "crawl" },
];

function formatDate(iso?: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

async function loadMessages() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/admin/dlq", {
      query: { queue: selectedQueue.value },
    });
    messages.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

async function replayAll() {
  replaying.value = true;
  try {
    const ids = messages.value.map((m) => m.id);
    await api.post("/api/v1/admin/dlq/replay", { body: { ids } });
    toast.add({ severity: "success", summary: "Messages replayed", life: 3000 });
    await loadMessages();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    replaying.value = false;
  }
}

async function discardAll() {
  discarding.value = true;
  try {
    const ids = messages.value.map((m) => m.id);
    await api.post("/api/v1/admin/dlq/discard", { body: { ids } });
    toast.add({ severity: "success", summary: "Messages discarded", life: 3000 });
    await loadMessages();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    discarding.value = false;
  }
}

async function runRetention() {
  retentionRunning.value = true;
  retentionResult.value = null;
  try {
    retentionResult.value = await api.post("/api/v1/admin/retention/run");
    toast.add({ severity: "success", summary: "Retention completed", life: 3000 });
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    retentionRunning.value = false;
  }
}

onMounted(() => {
  loadMessages();
});
</script>

<style scoped>
.dlq-toolbar {
  display: grid;
  grid-template-columns: minmax(12rem, 16rem) auto;
  gap: 0.75rem;
  align-items: end;
  margin-bottom: 1rem;
}

.dlq-field {
  display: grid;
  gap: 0.375rem;
}

.dlq-field label {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.dlq-toolbar :deep(.p-select) {
  width: 100%;
}

.dlq-reload {
  width: 2.5rem;
}

@media (max-width: 560px) {
  .dlq-toolbar {
    grid-template-columns: 1fr;
  }

  .dlq-reload {
    width: 100%;
  }
}
</style>
