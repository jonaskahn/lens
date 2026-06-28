export interface SessionData {
  scopes: string[];
  username?: string;
}

export const useAuth = () => {
  const authStore = useAuthStore();
  const router = useRouter();

  const login = async (apiKey: string) => {
    const result = await $fetch<{ scopes: string[] }>("/auth/login", {
      method: "POST",
      body: { api_key: apiKey },
    });
    authStore.setScopes(result.scopes);
    authStore.setAuthenticated(true);
    return result;
  };

  const logout = async () => {
    await $fetch("/auth/logout", { method: "POST" });
    authStore.clear();
    await router.push("/login");
  };

  const isAuthenticated = computed(() => authStore.isAuthenticated);
  const scopes = computed(() => authStore.scopes);

  const hasScope = (scope: string) => {
    return scopes.value.includes(scope);
  };

  return {
    login,
    logout,
    isAuthenticated,
    scopes,
    hasScope,
  };
};
