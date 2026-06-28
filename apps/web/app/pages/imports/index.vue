<template>
  <div>
    <AppPageHeader eyebrow="Setup portability" title="Import / Export">
      Bring a setup in from another lens instance, or export the current one — domains, URLs, channels, and bindings — as a single JSON file.
    </AppPageHeader>

    <Card class="mt-3">
      <template #title>Import Setup</template>
      <template #content>
        <div class="import-form">
          <div class="import-field">
            <label>Upload setup file</label>
            <FileUpload
              mode="basic"
              accept=".json,.yaml,.yml,.csv"
              :max-file-size="10_000_000"
              :custom-upload="true"
              choose-label="Choose File"
              class="w-full"
              @select="onFileSelect"
            />
          </div>

          <div v-if="selectedFile" class="selected-file">
            Selected: <strong>{{ selectedFile.name }}</strong> ({{ formatSize(selectedFile.size) }})
          </div>

          <div class="import-field import-field--narrow">
            <label for="import-conflict">On conflict</label>
            <Select
              v-model="onConflict"
              input-id="import-conflict"
              :options="conflictOptions"
              option-label="label"
              option-value="value"
              class="import-select"
            />
          </div>

          <Button
            label="Import"
            icon="pi pi-upload"
            :loading="importing"
            :disabled="!selectedFile"
            class="import-action"
            @click="doImport"
          />

          <Message v-if="importResult" severity="success" :closable="false">
            <div v-for="(value, key) in importResult" :key="key">
              {{ key }}: {{ value }}
            </div>
          </Message>
        </div>
      </template>
    </Card>

    <Card class="mt-3">
      <template #title>Export</template>
      <template #content>
        <div class="export-bar">
          <div class="export-field">
            <label for="import-export-domain">Domain</label>
            <Select
              v-model="exportDomain"
              input-id="import-export-domain"
              :options="exportDomainOptions"
              option-label="label"
              option-value="value"
              show-clear
              placeholder="All domains"
              class="w-full"
            />
          </div>
          <Button
            label="Export"
            icon="pi pi-download"
            :loading="exporting"
            @click="doExport"
          />
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ["scope"],
  scope: "write",
});

const api = useApi();
const toast = useToast();

const selectedFile = ref<File | null>(null);
const onConflict = ref("skip");
const importing = ref(false);
const exportDomain = ref<string>("");
const exporting = ref(false);
const importResult = ref<Record<string, unknown> | null>(null);

const conflictOptions = [
  { label: "Skip existing", value: "skip" },
  { label: "Merge", value: "merge" },
  { label: "Replace", value: "replace" },
];

const domainOptions = ref<Array<{ label: string; value: string }>>([]);

const exportDomainOptions = computed(() => [
  { label: "All domains", value: "" },
  ...domainOptions.value,
]);

function onFileSelect(event: { files: FileList | File[] }) {
  const files = Array.isArray(event.files) ? event.files : Array.from(event.files);
  selectedFile.value = files[0] ?? null;
  importResult.value = null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function doImport() {
  if (!selectedFile.value) return;
  importing.value = true;
  importResult.value = null;
  try {
    const ext = selectedFile.value.name.split(".").pop()?.toLowerCase();
    const contentTypes: Record<string, string> = {
      json: "application/json",
      yaml: "application/x-yaml",
      yml: "application/x-yaml",
      csv: "text/csv",
    };
    const contentType = contentTypes[ext ?? ""] ?? "application/json";
    const textContent = await selectedFile.value.text();

    let body: unknown;
    if (contentType === "application/json") {
      body = JSON.parse(textContent);
    } else {
      body = textContent;
    }

    const res = await api.post<Record<string, unknown>>("/api/v1/imports", {
      query: { on_conflict: onConflict.value },
      headers: { "content-type": contentType },
      body,
    });
    importResult.value = res ?? {};
    toast.add({ severity: "success", summary: "Import completed", life: 3000 });
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    importing.value = false;
  }
}

async function doExport() {
  exporting.value = true;
  try {
    const query: Record<string, string> = {};
    if (exportDomain.value) query.domain = exportDomain.value;

    const res = await api.get<Record<string, unknown>>("/api/v1/exports", { query });

    const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lens-export-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.add({ severity: "success", summary: "Export downloaded", life: 3000 });
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    exporting.value = false;
  }
}

async function loadDomains() {
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>("/api/v1/domains", {
      query: { limit: 200 },
    });
    domainOptions.value = (res.items ?? []).map((d) => ({
      label: d.host as string,
      value: d.host as string,
    }));
  } catch {
    // silently ignore domains load errors
  }
}

onMounted(() => {
  loadDomains();
});
</script>

<style scoped>
.import-form {
  display: grid;
  gap: 1rem;
  max-width: 36rem;
}

.import-field {
  display: grid;
  gap: 0.375rem;
}

.import-field--narrow {
  max-width: 15rem;
}

.import-field label,
.export-field label {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.selected-file {
  border: 1px solid var(--lens-graticule);
  border-radius: var(--lens-radius);
  color: var(--lens-ink-soft);
  font-size: 0.875rem;
  padding: 0.75rem 0.875rem;
  background: color-mix(in srgb, var(--lens-panel) 86%, transparent);
}

.import-action {
  justify-self: start;
}

.import-select {
  width: min(100%, 15rem);
}

.export-bar {
  display: grid;
  grid-template-columns: minmax(14rem, 24rem) auto;
  gap: 0.75rem;
  align-items: end;
}

.export-bar :deep(.p-select) {
  width: 100%;
}

.export-field {
  display: grid;
  gap: 0.375rem;
}

@media (max-width: 560px) {
  .import-form,
  .import-field--narrow,
  .import-select,
  .import-action,
  .export-bar :deep(.p-button) {
    width: 100%;
  }

  .import-action {
    justify-self: stretch;
  }

  .export-bar {
    grid-template-columns: 1fr;
  }
}
</style>
