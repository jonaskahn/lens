export const useAuthStore = defineStore("auth", () => {
  const isAuthenticated = ref(false);
  const scopes = ref<string[]>([]);

  const setAuthenticated = (value: boolean) => {
    isAuthenticated.value = value;
  };

  const setScopes = (newScopes: string[]) => {
    scopes.value = newScopes;
  };

  const clear = () => {
    isAuthenticated.value = false;
    scopes.value = [];
  };

  return {
    isAuthenticated,
    scopes,
    setAuthenticated,
    setScopes,
    clear,
  };
});
