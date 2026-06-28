<template>
  <div>
    <AppPageHeader eyebrow="Admin · runtime config" title="Dynamic settings">
      <template #actions>
        <Button label="Reload all instances" icon="pi pi-sync" :loading="reloading" @click="reloadConfig" />
      </template>
    </AppPageHeader>

    <div class="flex gap-2 mb-3">
      <Button label="Reload All Instances" icon="pi pi-sync" :loading="reloading" @click="reloadConfig" />
    </div>

    <DataTable :value="settings" :loading="loading" paginator :rows="20" striped-rows>
      <Column field="key" header="Key" sortable />
      <Column field="value" header="Effective Value" />
      <Column field="source" header="Source">
        <template #body="{ data }">
          <Tag
            :severity="sourceSeverity(data.source as string)"
            :value="data.source"
          />
        </template>
      </Column>
      <Column field="reload_policy" header="Policy">
        <template #body="{ data }">
          <Tag
            :severity="(data.reload_policy as string) === 'hot' ? 'success' : (data.reload_policy as string) === 'restart' ? 'warn' : 'info'"
            :value="data.reload_policy"
          />
        </template>
      </Column>
      <Column field="mutable" header="Mutable">
        <template #body="{ data }">
          <Tag :severity="data.mutable ? 'success' : 'danger'" :value="data.mutable ? 'Yes' : 'No'" />
        </template>
      </Column>
      <Column field="description" header="Description" />
      <Column header="Actions">
        <template #body="{ data }">
          <Button
            v-if="data.mutable"
            icon="pi pi-pencil"
            severity="secondary"
            text
            rounded
            aria-label="Edit"
            @click="editSetting(data)"
          />
        </template>
      </Column>
    </DataTable>

    <Dialog
      v-model:visible="showEdit"
      header="Edit Setting"
      :modal="true"
      class="w-full max-w-lg"
    >
      <div class="flex flex-col gap-3">
        <div><strong>Key:</strong> {{ editForm.key }}</div>
        <div><strong>Current Value:</strong> {{ editForm.current_value }}</div>
        <div><strong>Reload Policy:</strong>
          <Tag
            :severity="editForm.reload_policy === 'hot' ? 'success' : 'warn'"
            :value="editForm.reload_policy"
          />
        </div>
        <div>
          <label class="block mb-1">New Value</label>
          <InputText v-model="editForm.new_value" class="w-full" />
          <small class="text-surface-500">{{ editForm.reload_policy === 'restart' ? 'Requires instance restart' : 'Takes effect immediately (hot)' }}</small>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showEdit = false" />
        <Button label="Save" :loading="saving" @click="saveSetting" />
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

const settings = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const showEdit = ref(false);
const saving = ref(false);
const reloading = ref(false);

const editForm = reactive({
  key: "",
  current_value: "",
  reload_policy: "",
  new_value: "",
});

function sourceSeverity(source: string): "success" | "info" | "warn" {
  if (source === "db") return "success";
  if (source === "env") return "warn";
  return "info";
}

async function loadSettings() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/admin/settings", {
      query: { limit: 200 },
    });
    settings.value = (res.items ?? []).sort(
      (a, b) => ((a.key as string) ?? "").localeCompare((b.key as string) ?? ""),
    );
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

function editSetting(data: Record<string, unknown>) {
  editForm.key = data.key as string;
  editForm.current_value = String(data.value ?? "");
  editForm.reload_policy = data.reload_policy as string;
  editForm.new_value = "";
  showEdit.value = true;
}

async function saveSetting() {
  saving.value = true;
  try {
    await api.put(`/api/v1/admin/settings/${editForm.key}`, {
      body: { value: parseSettingValue(editForm.new_value) },
    });
    toast.add({ severity: "success", summary: "Setting updated", life: 3000 });
    showEdit.value = false;
    await loadSettings();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    saving.value = false;
  }
}

async function reloadConfig() {
  reloading.value = true;
  try {
    await api.post("/api/v1/admin/settings/reload");
    toast.add({ severity: "success", summary: "Reload broadcast sent to all instances", life: 3000 });
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    reloading.value = false;
  }
}

function parseSettingValue(val: string): string | number | boolean {
  if (val === "true") return true;
  if (val === "false") return false;
  if (/^-?\d+$/.test(val)) return parseInt(val, 10);
  if (/^-?\d+\.\d+$/.test(val)) return parseFloat(val);
  return val;
}

onMounted(() => {
  loadSettings();
});
</script>
