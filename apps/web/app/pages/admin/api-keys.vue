<template>
  <div>
    <AppPageHeader eyebrow="Admin · credentials" title="API keys">
      Keys issued to operators and machines. Each plaintext is shown once at creation and stored only as a hash.
      <template #actions>
        <Button label="Create key" icon="pi pi-plus" @click="openCreateDialog" />
      </template>
    </AppPageHeader>

    <DataTable :value="keys" :loading="loading" paginator :rows="20" striped-rows class="mt-3">
      <Column field="key_id" header="Key ID" />
      <Column field="scopes" header="Scopes">
        <template #body="{ data }">
          <div class="flex gap-1 flex-wrap">
            <Tag
              v-for="scope in (data.scopes as string[])"
              :key="scope"
              severity="info"
              :value="scope"
            />
          </div>
        </template>
      </Column>
      <Column field="created_at" header="Created">
        <template #body="{ data }">
          {{ formatDate(data.created_at as string) }}
        </template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            aria-label="Revoke"
            @click="confirmRevoke(data)"
          />
        </template>
      </Column>
    </DataTable>

    <Dialog
      v-model:visible="showCreate"
      header="Create API Key"
      :modal="true"
      :draggable="false"
      :resizable="false"
      :style="{ width: '34rem' }"
      :breakpoints="{ '640px': 'calc(100vw - 2rem)' }"
      class="api-key-dialog"
    >
      <div class="api-key-form">
        <div class="api-key-field">
          <label>Scopes</label>
          <div class="scope-grid">
            <div v-for="scope in availableScopes" :key="scope" class="scope-option">
              <Checkbox v-model="createForm.scopes" :value="scope" :input-id="`sc-${scope}`" />
              <label :for="`sc-${scope}`">{{ scope }}</label>
            </div>
          </div>
        </div>

        <div v-if="createdKey">
          <Message severity="success">
            <p class="created-key-title">Key created. Copy it now - it won't be shown again:</p>
            <code class="created-key-value">{{ createdKey }}</code>
          </Message>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="closeCreateDialog" />
        <Button label="Create key" :loading="creating" :disabled="createForm.scopes.length === 0" @click="createKey" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "admin",
});

const api = useApi();
const toast = useToast();
const confirm = useConfirm();

const keys = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const showCreate = ref(false);
const creating = ref(false);
const createdKey = ref("");

const availableScopes = ["read", "write", "admin"];

const createForm = reactive({
  scopes: ["read", "write"],
});

function openCreateDialog() {
  createForm.scopes = ["read", "write"];
  createdKey.value = "";
  showCreate.value = true;
}

function closeCreateDialog() {
  showCreate.value = false;
  createdKey.value = "";
}

function formatDate(iso?: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

async function loadKeys() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/admin/api-keys", {
      query: { limit: 200 },
    });
    keys.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

async function createKey() {
  creating.value = true;
  createdKey.value = "";
  try {
    const res = await api.post<{ plaintext: string }>("/api/v1/admin/api-keys", {
      body: { scopes: createForm.scopes },
    });
    createdKey.value = res.plaintext ?? "";
    toast.add({ severity: "success", summary: "API key created", life: 3000 });
    await loadKeys();
  } catch (err) {
    handleApiError(err, toast);
    showCreate.value = false;
  } finally {
    creating.value = false;
  }
}

function confirmRevoke(data: Record<string, unknown>) {
  confirm.require({
    message: `Revoke key "${data.key_id}"? This cannot be undone.`,
    header: "Confirm Revocation",
    icon: "pi pi-exclamation-triangle",
    accept: async () => {
      try {
        await api.del(`/api/v1/admin/api-keys/${data.id}`);
        toast.add({ severity: "success", summary: "Key revoked", life: 3000 });
        await loadKeys();
      } catch (err) {
        handleApiError(err, toast);
      }
    },
  });
}

onMounted(() => {
  loadKeys();
});
</script>

<style scoped>
:deep(.api-key-dialog) {
  max-width: calc(100vw - 2rem);
}

:deep(.api-key-dialog .p-dialog-header) {
  border-bottom: 1px solid var(--lens-graticule);
  padding-bottom: 0.875rem;
}

:deep(.api-key-dialog .p-dialog-content) {
  padding-top: 1rem;
}

.api-key-form {
  display: grid;
  gap: 1rem;
}

.api-key-field {
  display: grid;
  gap: 0.625rem;
}

.api-key-field > label,
.scope-option label {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.scope-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.625rem;
}

.scope-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid var(--lens-graticule);
  border-radius: var(--lens-radius);
  padding: 0.75rem;
  background: color-mix(in srgb, var(--lens-panel) 86%, transparent);
}

.created-key-title {
  font-weight: 600;
  margin: 0 0 0.375rem;
}

.created-key-value {
  display: block;
  overflow-wrap: anywhere;
  font-size: 0.8125rem;
}

:deep(.p-dialog-footer) {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
}

@media (max-width: 520px) {
  .scope-grid {
    grid-template-columns: 1fr;
  }

  :deep(.p-dialog-footer .p-button) {
    flex: 1 1 100%;
  }
}
</style>
