export const useUiStore = defineStore("ui", () => {
  const sidebarVisible = ref(true);

  const toggleSidebar = () => {
    sidebarVisible.value = !sidebarVisible.value;
  };

  return {
    sidebarVisible,
    toggleSidebar,
  };
});
