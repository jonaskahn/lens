<template>
  <div>
    <AppPageHeader :title="(domain?.host as string) ?? 'Domain'">
      <template #eyebrow>
        <NuxtLink to="/domains" class="back-link">← Domains</NuxtLink>
        <span class="hint">· categories live under a domain</span>
      </template>
      <template #actions>
        <Button
          v-if="auth.hasScope('write')"
          label="Add category"
          icon="pi pi-plus"
          @click="showCreate = true"
        />
      </template>
    </AppPageHeader>

    <Card v-if="domain" class="mt-3">
      <template #content>
        <div class="grid grid-cols-2 gap-2">
          <div><strong>Host:</strong> {{ domain.host }}</div>
          <div><strong>Display Name:</strong> {{ domain.display_name ?? "-" }}</div>
          <div>
            <strong>Enabled:</strong>
            <Tag :severity="domain.enabled ? 'success' : 'secondary'">
              {{ domain.enabled ? "Yes" : "No" }}
            </Tag>
          </div>
          <div>
            <strong>Politeness:</strong>
            max_concurrency: {{ (domain.politeness as Record<string, number>)?.["max_concurrency"] ?? "-" }},
            min_delay_ms: {{ (domain.politeness as Record<string, number>)?.["min_delay_ms"] ?? "-" }}
          </div>
        </div>
      </template>
    </Card>

    <h2 class="text-xl font-semibold mt-4 mb-2">Categories</h2>
    <DataTable :value="categories" :loading="catLoading" striped-rows>
      <Column field="name" header="Name" />
      <Column field="description" header="Description" />
      <Column header="Actions">
        <template #body="{ data }">
          <Button icon="pi pi-pencil" severity="secondary" text rounded aria-label="Edit" @click="editCategory(data)" />
          <Button icon="pi pi-trash" severity="danger" text rounded aria-label="Delete" @click="confirmDeleteCategory(data)" />
        </template>
      </Column>
    </DataTable>

    <Dialog
      v-model:visible="showCreate"
      :header="editCatId ? 'Edit Category' : 'Add Category'"
      :modal="true"
      class="w-full max-w-lg"
    >
      <div class="flex flex-col gap-3">
        <div>
          <label class="block mb-1">Name</label>
          <InputText v-model="catForm.name" class="w-full" :disabled="!!editCatId" />
        </div>
        <div>
          <label class="block mb-1">Description</label>
          <Textarea v-model="catForm.description" class="w-full" rows="2" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showCreate = false" />
        <Button label="Save" :loading="catSaving" @click="saveCategory" />
      </template>
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
const confirm = useConfirm();

const domain = ref<Record<string, unknown> | null>(null);
const categories = ref<Array<Record<string, unknown>>>([]);
const catLoading = ref(false);
const showCreate = ref(false);
const catSaving = ref(false);
const editCatId = ref<string | null>(null);

const catForm = reactive({
  name: "",
  description: "",
});

async function loadDomain() {
  try {
    domain.value = await api.get<Record<string, unknown>>(`/api/v1/domains/${route.params.id as string}`);
  } catch (err) {
    handleApiError(err, toast);
  }
}

async function loadCategories() {
  catLoading.value = true;
  try {
    const res = await api.get<{ items: Array<Record<string, unknown>> }>(
      `/api/v1/domains/${route.params.id as string}/categories`,
    );
    categories.value = res.items ?? [];
  } catch {
    // silently ignore categories load errors
  } finally {
    catLoading.value = false;
  }
}

function editCategory(data: Record<string, unknown>) {
  editCatId.value = data.id as string;
  catForm.name = data.name as string;
  catForm.description = (data.description as string) ?? "";
  showCreate.value = true;
}

async function saveCategory() {
  catSaving.value = true;
  try {
    const body: Record<string, string> = { name: catForm.name };
    if (catForm.description) body.description = catForm.description;

    if (editCatId.value) {
      await api.patch(`/api/v1/categories/${editCatId.value}`, { body });
      toast.add({ severity: "success", summary: "Category updated", life: 3000 });
    } else {
      await api.post(`/api/v1/domains/${route.params.id as string}/categories`, { body });
      toast.add({ severity: "success", summary: "Category created", life: 3000 });
    }

    showCreate.value = false;
    editCatId.value = null;
    catForm.name = "";
    catForm.description = "";
    await loadCategories();
  } catch (err) {
    handleApiError(err, toast);
  } finally {
    catSaving.value = false;
  }
}

function confirmDeleteCategory(data: Record<string, unknown>) {
  confirm.require({
    message: `Delete category "${data.name}"?`,
    header: "Confirm Deletion",
    icon: "pi pi-exclamation-triangle",
    accept: async () => {
      try {
        await api.del(`/api/v1/categories/${data.id as string}`);
        toast.add({ severity: "success", summary: "Category deleted", life: 3000 });
        await loadCategories();
      } catch (err) {
        handleApiError(err, toast);
      }
    },
  });
}

onMounted(() => {
  loadDomain();
  loadCategories();
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
.hint {
  color: var(--lens-graph);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.6875rem;
}
</style>
