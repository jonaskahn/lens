export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore();
  try {
    const requestFetch = useRequestFetch();
    const session = await requestFetch<{ scopes: string[]; username?: string }>("/api/auth/session");
    authStore.setScopes(session.scopes);
    authStore.setAuthenticated(true);
  } catch {
    authStore.clear();
  }
});
