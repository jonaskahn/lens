export default defineNuxtRouteMiddleware((to) => {
  const authStore = useAuthStore();
  const scopeRequired = to.meta.scope as string | undefined;

  if (scopeRequired && !authStore.scopes.includes(scopeRequired)) {
    throw createError({
      statusCode: 403,
      statusMessage: `This page requires the "${scopeRequired}" scope`,
    });
  }
});
