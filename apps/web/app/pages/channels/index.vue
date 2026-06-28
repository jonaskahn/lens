<template>
  <div>
    <AppPageHeader eyebrow="Notifications" title="Channels">
      Where lens sends a change, an error, or a no-change heartbeat — wired up against the Apprise URL of each target.
      <template #actions>
        <Button
          v-if="auth.hasScope('write')"
          label="Add channel"
          icon="pi pi-plus"
          @click="openCreateDialog"
        />
      </template>
    </AppPageHeader>

    <DataTable :value="channels" :loading="loading" paginator :rows="20" striped-rows class="mt-3">
      <Column field="name" header="Name" />
      <Column field="kind" header="Kind">
        <template #body="{ data }">
          <Tag severity="info" :value="data.kind" />
        </template>
      </Column>
      <Column field="enabled" header="Enabled">
        <template #body="{ data }">
          <Tag :severity="data.enabled ? 'success' : 'secondary'">
            {{ data.enabled ? "Yes" : "No" }}
          </Tag>
        </template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <Button
            icon="pi pi-send"
            severity="info"
            text
            rounded
            aria-label="Send test"
            @click="testNotify(data)"
          />
          <Button
            v-if="data.enabled"
            icon="pi pi-pause"
            severity="warn"
            text
            rounded
            aria-label="Disable"
            @click="toggleChannel(data, false)"
          />
          <Button
            v-else
            icon="pi pi-play"
            severity="success"
            text
            rounded
            aria-label="Enable"
            @click="toggleChannel(data, true)"
          />
          <Button
            icon="pi pi-pencil"
            severity="secondary"
            text
            rounded
            aria-label="Edit"
            @click="editChannel(data)"
          />
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            aria-label="Delete"
            @click="confirmDelete(data)"
          />
        </template>
      </Column>
    </DataTable>

    <Dialog
      v-model:visible="showCreate"
      :header="editingId ? 'Edit Channel' : 'Add Channel'"
      :modal="true"
      :draggable="false"
      :resizable="false"
      :style="{ width: '34rem' }"
      :breakpoints="{ '640px': 'calc(100vw - 2rem)' }"
      class="channel-dialog"
    >
      <div class="channel-form">
        <div class="channel-field">
          <label for="channel-name">Name</label>
          <InputText id="channel-name" v-model="form.name" class="w-full" placeholder="Ops alerts" />
        </div>
        <div class="channel-field">
          <label for="channel-kind">Kind</label>
          <Select
            v-model="form.kind"
            input-id="channel-kind"
            :options="kindOptions"
            option-label="label"
            option-value="value"
            class="w-full"
            placeholder="Select kind"
          />
        </div>
        <div class="channel-field">
          <label for="channel-apprise-url">Apprise URL</label>
          <Password
            v-model="form.apprise_url"
            input-id="channel-apprise-url"
            :feedback="false"
            toggle-mask
            class="channel-password"
            input-class="channel-password-input"
            placeholder="apprise://..."
          />
          <small>This value is encrypted and never displayed again.</small>
        </div>
        <div class="channel-toggle">
          <ToggleSwitch v-model="form.enabled" input-id="channel-enabled" />
          <label for="channel-enabled">Enabled</label>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="showCreate = false" />
        <Button :label="editingId ? 'Save changes' : 'Create channel'" :loading="saving" @click="saveChannel" />
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

const channels = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);
const editingId = ref<string | null>(null);

const kindOptions = [
  { label: "Email", value: "email" },
  { label: "Slack", value: "slack" },
  { label: "Discord", value: "discord" },
  { label: "Telegram", value: "telegram" },
  { label: "Webhook", value: "webhook" },
];

const form = reactive({
  name: "",
  kind: "slack",
  apprise_url: "",
  enabled: true,
});

function openCreateDialog() {
  resetForm();
  showCreate.value = true;
}

async function loadChannels() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/channels", {
      query: { limit: 200 },
    });
    channels.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

function editChannel(data: Record<string, unknown>) {
  editingId.value = data.id as string;
  form.name = data.name as string;
  form.kind = data.kind as string;
  form.apprise_url = "";
  form.enabled = (data.enabled as boolean) ?? true;
  showCreate.value = true;
}

async function saveChannel() {
  saving.value = true;
  try {
    const body: Record<string, unknown> = {
      name: form.name,
      kind: form.kind,
      enabled: form.enabled,
    };
    if (form.apprise_url) body.apprise_url = form.apprise_url;

    if (editingId.value) {
      await api.patch(`/api/v1/channels/${editingId.value}`, { body });
      toast.add({ severity: "success", summary: "Channel updated", life: 3000 });
    } else {
      await api.post("/api/v1/channels", { body });
      toast.add({ severity: "success", summary: "Channel created", life: 3000 });
    }

    showCreate.value = false;
    resetForm();
    await loadChannels();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    saving.value = false;
  }
}

async function toggleChannel(data: Record<string, unknown>, enabled: boolean) {
  try {
    await api.patch(`/api/v1/channels/${data.id}`, {
      body: { enabled },
    });
    toast.add({
      severity: "success",
      summary: enabled ? "Channel enabled" : "Channel disabled",
      life: 3000,
    });
    await loadChannels();
  } catch (err) {
    handleApiError(err, toast);
  }
}

async function testNotify(data: Record<string, unknown>) {
  try {
    await api.post(`/api/v1/channels/${data.id}/test`);
    toast.add({ severity: "success", summary: "Test notification sent", life: 3000 });
  } catch (err) {
    handleApiError(err, toast);
  }
}

function confirmDelete(data: Record<string, unknown>) {
  confirm.require({
    message: `Delete channel "${data.name}"?`,
    header: "Confirm Deletion",
    icon: "pi pi-exclamation-triangle",
    accept: async () => {
      try {
        await api.del(`/api/v1/channels/${data.id}`);
        toast.add({ severity: "success", summary: "Channel deleted", life: 3000 });
        await loadChannels();
      } catch (err) {
        handleApiError(err, toast);
      }
    },
  });
}

function resetForm() {
  editingId.value = null;
  form.name = "";
  form.kind = "slack";
  form.apprise_url = "";
  form.enabled = true;
}

onMounted(() => {
  loadChannels();
});
</script>

<style scoped>
:deep(.channel-dialog) {
  max-width: calc(100vw - 2rem);
}

:deep(.channel-dialog .p-dialog-header) {
  border-bottom: 1px solid var(--lens-graticule);
  padding-bottom: 0.875rem;
}

:deep(.channel-dialog .p-dialog-content) {
  padding-top: 1rem;
}

.channel-form {
  display: grid;
  gap: 1rem;
}

.channel-field {
  display: grid;
  gap: 0.375rem;
}

.channel-field label,
.channel-toggle label {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.channel-field small {
  color: var(--lens-graph);
  line-height: 1.4;
}

:deep(.channel-password) {
  display: flex;
  position: relative;
  width: 100%;
}

:deep(.channel-password .p-password-input) {
  flex: 1;
  min-width: 0;
  width: 100%;
  padding-inline-end: 2.75rem;
}

:deep(.channel-password .p-password-toggle-mask-icon) {
  position: absolute;
  inset-inline-end: 0.875rem;
  top: 50%;
  transform: translateY(-50%);
  margin: 0;
}

.channel-toggle {
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
