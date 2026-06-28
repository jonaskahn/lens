<template>
  <div>
    <AppPageHeader eyebrow="Tracked hosts" title="Domains">
      <template #actions>
        <Button
          v-if="auth.hasScope('write')"
          label="Add domain"
          icon="pi pi-plus"
          @click="openCreateDialog"
        />
      </template>
    </AppPageHeader>

    <div class="table-shell mt-3">
      <DataTable
        :value="domains"
        :loading="loading"
        paginator
        :rows="20"
      >
        <Column field="host" header="Host" sortable />
        <Column field="display_name" header="Display Name" />
        <Column field="enabled" header="Enabled">
          <template #body="{ data }">
            <Tag :severity="data.enabled ? 'success' : 'secondary'">
              {{ data.enabled ? "Yes" : "No" }}
            </Tag>
          </template>
        </Column>
        <Column header="Actions">
          <template #body="{ data }">
            <div class="row-actions">
              <Button icon="pi pi-pencil" severity="secondary" text rounded aria-label="Edit" @click="editDomain(data)" />
              <Button icon="pi pi-trash" severity="danger" text rounded aria-label="Delete" @click="confirmDelete(data)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <Dialog
      v-model:visible="showCreate"
      :header="editingId ? 'Edit Domain' : 'Add Domain'"
      :modal="true"
      :draggable="false"
      :resizable="false"
      :style="{ width: '34rem' }"
      :breakpoints="{ '640px': 'calc(100vw - 2rem)' }"
      class="domain-dialog"
    >
      <div class="domain-form">
        <div class="domain-field">
          <label for="domain-host">Host</label>
          <InputText id="domain-host" v-model="form.host" class="w-full" :disabled="!!editingId" placeholder="example.com" />
        </div>
        <div class="domain-field">
          <label for="domain-display-name">Display Name</label>
          <InputText id="domain-display-name" v-model="form.display_name" class="w-full" placeholder="Optional label" />
        </div>
        <div class="domain-toggle">
          <ToggleSwitch v-model="form.enabled" input-id="enabled" />
          <label for="enabled">Enabled</label>
        </div>
        <div class="domain-field">
          <label for="domain-delay">Politeness delay</label>
          <InputNumber
            id="domain-delay"
            v-model="form.politeness_min_delay_ms"
            class="w-full"
            input-class="w-full"
            :min="0"
            suffix=" ms"
          />
          <small>Minimum delay between requests for this host.</small>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="showCreate = false" />
        <Button :label="editingId ? 'Save changes' : 'Create domain'" :loading="saving" @click="saveDomain" />
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

const domains = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const editingId = ref<string | null>(null);

const form = reactive({
  host: "",
  display_name: "",
  enabled: true,
  politeness_min_delay_ms: 1000,
});

function openCreateDialog() {
  resetForm();
  showCreate.value = true;
}

async function loadDomains() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/domains", {
      query: { limit: 200 },
    });
    domains.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

function editDomain(data: Record<string, unknown>) {
  editingId.value = data.id as string;
  form.host = data.host as string;
  form.display_name = (data.display_name as string) ?? "";
  form.enabled = (data.enabled as boolean) ?? true;
  form.politeness_min_delay_ms = ((data.politeness as Record<string, number>)?.min_delay_ms) ?? 1000;
  showCreate.value = true;
}

async function saveDomain() {
  saving.value = true;
  try {
    const body: Record<string, unknown> = {
      host: form.host,
      enabled: form.enabled,
      politeness: { min_delay_ms: form.politeness_min_delay_ms },
    };
    if (form.display_name) body.display_name = form.display_name;

    if (editingId.value) {
      await api.put(`/api/v1/domains/${editingId.value}`, { body });
      toast.add({ severity: "success", summary: "Domain updated", life: 3000 });
    } else {
      await api.post("/api/v1/domains", { body });
      toast.add({ severity: "success", summary: "Domain created", life: 3000 });
    }

    showCreate.value = false;
    resetForm();
    await loadDomains();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    saving.value = false;
  }
}

function confirmDelete(data: Record<string, unknown>) {
  confirm.require({
    message: `Delete domain "${data.host}"? This will cascade-delete all categories and URLs.`,
    header: "Confirm Deletion",
    icon: "pi pi-exclamation-triangle",
    accept: async () => {
      try {
        await api.del(`/api/v1/domains/${data.id as string}`);
        toast.add({ severity: "success", summary: "Domain deleted", life: 3000 });
        await loadDomains();
      } catch (err) {
        handleApiError(err, toast);
      }
    },
  });
}

function resetForm() {
  editingId.value = null;
  form.host = "";
  form.display_name = "";
  form.enabled = true;
  form.politeness_min_delay_ms = 1000;
}

onMounted(() => {
  loadDomains();
});
</script>

<style scoped>
.table-shell {
  overflow-x: auto;
}

.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  white-space: nowrap;
}

:deep(.domain-dialog) {
  max-width: calc(100vw - 2rem);
}

:deep(.domain-dialog .p-dialog-header) {
  border-bottom: 1px solid var(--lens-graticule);
  padding-bottom: 0.875rem;
}

:deep(.domain-dialog .p-dialog-content) {
  padding-top: 1rem;
}

.domain-form {
  display: grid;
  gap: 1rem;
}

.domain-field {
  display: grid;
  gap: 0.375rem;
}

.domain-field label,
.domain-toggle label {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.domain-field small {
  color: var(--lens-graph);
  line-height: 1.4;
}

.domain-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid var(--lens-graticule);
  border-radius: var(--lens-radius);
  padding: 0.875rem;
  background: color-mix(in srgb, var(--lens-panel) 86%, transparent);
}

:deep(.p-dialog-footer) {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
}

@media (max-width: 520px) {
  :deep(.p-dialog-footer .p-button) {
    flex: 1 1 100%;
  }
}
</style>
