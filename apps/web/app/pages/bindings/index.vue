<template>
  <div>
    <AppPageHeader eyebrow="Routing rules" title="Bindings">
      Binding precedence is URL &gt; Category &gt; Domain &gt; Global — a more specific binding always wins, and the global binding is the fallback when nothing matches.
      <template #actions>
        <Button
          v-if="auth.hasScope('write')"
          label="Add binding"
          icon="pi pi-plus"
          @click="showCreate = true"
        />
      </template>
    </AppPageHeader>

    <DataTable :value="bindings" :loading="loading" paginator :rows="20" striped-rows class="mt-3">
      <Column field="scope" header="Scope">
        <template #body="{ data }">
          <Tag :severity="scopeSeverity(data.scope as string)" :value="data.scope" />
        </template>
      </Column>
      <Column field="scope_id" header="Scope ID">
        <template #body="{ data }">
          <code class="text-xs">{{ (data.scope_id as string)?.slice(0, 8) ?? "-" }}</code>
        </template>
      </Column>
      <Column field="on_change" header="On Change">
        <template #body="{ data }">
          <i :class="data.on_change ? 'pi pi-check text-green-500' : 'pi pi-times text-surface-400'" />
        </template>
      </Column>
      <Column field="on_error" header="On Error">
        <template #body="{ data }">
          <i :class="data.on_error ? 'pi pi-check text-green-500' : 'pi pi-times text-surface-400'" />
        </template>
      </Column>
      <Column field="on_no_change" header="On No Change">
        <template #body="{ data }">
          <i :class="data.on_no_change ? 'pi pi-check text-green-500' : 'pi pi-times text-surface-400'" />
        </template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
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
      header="Add Binding"
      :modal="true"
      class="w-full max-w-lg"
    >
      <div class="flex flex-col gap-3">
        <div>
          <label class="block mb-1">Channel</label>
          <Select
            v-model="form.channel_id"
            :options="channelOptions"
            option-label="label"
            option-value="value"
            class="w-full"
            placeholder="Select channel"
          />
        </div>
        <div>
          <label class="block mb-1">Scope</label>
          <Select
            v-model="form.scope"
            :options="scopeOptions"
            option-label="label"
            option-value="value"
            class="w-full"
            placeholder="Select scope"
          />
        </div>
        <div v-if="form.scope !== 'global'">
          <label class="block mb-1">Scope ID</label>
          <InputText v-model="form.scope_id" class="w-full" placeholder="UUID" />
        </div>
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <Checkbox v-model="form.on_change" input-id="on_change" binary />
            <label for="on_change">On Change</label>
          </div>
          <div class="flex items-center gap-2">
            <Checkbox v-model="form.on_error" input-id="on_error" binary />
            <label for="on_error">On Error</label>
          </div>
          <div class="flex items-center gap-2">
            <Checkbox v-model="form.on_no_change" input-id="on_no_change" binary />
            <label for="on_no_change">On No Change</label>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showCreate = false" />
        <Button label="Save" :loading="saving" @click="saveBinding" />
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

const bindings = ref<Array<Record<string, unknown>>>([]);
const channels = ref<Array<Record<string, unknown>>>([]);
const loading = ref(false);
const showCreate = ref(false);
const saving = ref(false);

const scopeOptions = [
  { label: "Global", value: "global" },
  { label: "Domain", value: "domain" },
  { label: "Category", value: "category" },
  { label: "URL", value: "url" },
];

const channelOptions = computed(() =>
  channels.value.map((c) => ({ label: c.name as string, value: c.id as string })),
);

const form = reactive({
  channel_id: "",
  scope: "global",
  scope_id: "",
  on_change: true,
  on_error: true,
  on_no_change: false,
});

function scopeSeverity(scope: string): "success" | "info" | "warn" | "danger" {
  const map: Record<string, "success" | "info" | "warn" | "danger"> = {
    global: "info",
    domain: "success",
    category: "warn",
    url: "danger",
  };
  return map[scope] ?? "info";
}

async function loadBindings() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/bindings", {
      query: { limit: 200 },
    });
    bindings.value = res.items ?? [];
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    loading.value = false;
  }
}

async function loadChannels() {
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/channels", {
      query: { limit: 200 },
    });
    channels.value = res.items ?? [];
  } catch {
    // silently ignore
  }
}

async function saveBinding() {
  saving.value = true;
  try {
    const body: Record<string, unknown> = {
      channel_id: form.channel_id,
      scope: form.scope,
      on_change: form.on_change,
      on_error: form.on_error,
      on_no_change: form.on_no_change,
    };
    if (form.scope !== "global" && form.scope_id) {
      body.scope_id = form.scope_id;
    }

    await api.post("/api/v1/bindings", { body });
    toast.add({ severity: "success", summary: "Binding created", life: 3000 });
    showCreate.value = false;
    resetForm();
    await loadBindings();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    saving.value = false;
  }
}

function confirmDelete(data: Record<string, unknown>) {
  confirm.require({
    message: `Delete binding for scope "${data.scope}"?`,
    header: "Confirm Deletion",
    icon: "pi pi-exclamation-triangle",
    accept: async () => {
      try {
        await api.del(`/api/v1/bindings/${data.id}`);
        toast.add({ severity: "success", summary: "Binding deleted", life: 3000 });
        await loadBindings();
      } catch (err) {
        handleApiError(err, toast);
      }
    },
  });
}

function resetForm() {
  form.channel_id = "";
  form.scope = "global";
  form.scope_id = "";
  form.on_change = true;
  form.on_error = true;
  form.on_no_change = false;
}

onMounted(() => {
  loadChannels();
  loadBindings();
});
</script>

<style scoped>
</style>
