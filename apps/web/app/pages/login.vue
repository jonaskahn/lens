<template>
  <div class="entry">
    <header class="entry__brand">
      <span class="reticle reticle--lg" aria-hidden="true" />
      <span class="entry__wordmark">lens</span>
      <span class="entry__wordmark-sub">change watch console</span>
    </header>

    <div class="entry__card">
      <div class="entry__eyebrow eyebrow">Operator sign-in</div>
      <h1 class="entry__title">
        Point <span class="entry__title-focus">lens</span> at the pages that change
      </h1>
      <p class="entry__lede">
        Sign in with your API key to start watching. The key never leaves this machine — it is
        sealed into your session scope and routed through the operator proxy.
      </p>

      <form class="entry__form" @submit.prevent="handleLogin">
        <label class="field">
          <span class="field__label">API key</span>
          <Password
            v-model="apiKey"
            :feedback="false"
            toggle-mask
            input-class="field__input"
            class="field__control"
            placeholder="paste your API key"
            autocomplete="off"
            @keyup.enter.prevent="handleLogin"
          />
        </label>

        <Button
          type="submit"
          label="Sign in"
          icon="pi pi-arrow-right"
          icon-pos="right"
          :loading="loading"
          class="entry__submit"
        />

        <Message
          v-if="loginError"
          severity="error"
          :closable="false"
          class="entry__error"
        >
          {{ loginError }}
        </Message>
      </form>
    </div>

    <ul class="entry__spec">
      <li><span class="data-mono">scope</span> session-sealed per operator</li>
      <li><span class="data-mono">key</span> never reaches the browser bundle</li>
      <li><span class="data-mono">proxy</span> CSRF-protected mutations</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: "auth",
  auth: { unauthenticatedOnly: true },
});

const apiKey = ref("");
const loading = ref(false);
const loginError = ref("");

async function handleLogin() {
  if (!apiKey.value || loading.value) return;
  loading.value = true;
  loginError.value = "";
  try {
    const auth = useAuth();
    await auth.login(apiKey.value);
    await navigateTo("/");
  } catch (err: unknown) {
    const msg = (err as { data?: { error?: { message?: string } } })?.data?.error?.message;
    loginError.value = msg || "That key was rejected, or the backend isn't reachable. Try again.";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.entry {
  width: 100%;
  max-width: 30rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.entry__brand {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 0.625rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--lens-graticule);
}
.entry__wordmark {
  font-family: var(--font-display);
  font-size: 1.75rem;
  line-height: 1;
  font-weight: 500;
  letter-spacing: -0.02em;
}
.entry__wordmark-sub {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.625rem;
  color: var(--lens-graph);
}
.entry__card {
  background: var(--lens-panel);
  border: 1px solid var(--lens-graticule);
  border-radius: var(--lens-radius);
  padding: clamp(1.5rem, 1rem + 1.5vw, 2.25rem);
}
.entry__eyebrow {
  margin-bottom: 0.75rem;
}
.entry__title {
  font-family: var(--font-display);
  font-weight: 500;
  font-size: clamp(1.625rem, 1.2rem + 1.2vw, 2.125rem);
  line-height: 1.1;
  letter-spacing: -0.015em;
  margin: 0 0 0.75rem;
  color: var(--lens-ink);
}
.entry__title-focus {
  color: var(--lens-primary);
  font-style: italic;
}
.entry__lede {
  margin: 0 0 1.5rem;
  color: var(--lens-ink-soft);
  font-size: 0.875rem;
  line-height: 1.55;
  max-width: 42ch;
}
.entry__form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.field__label {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.625rem;
  color: var(--lens-graph);
}
.field__control {
  width: 100%;
}
.field__control :deep(.p-password) {
  display: flex;
  width: 100%;
}
.field__control :deep(.p-password-input) {
  flex: 1;
  min-width: 0;
}
.entry__submit {
  align-self: flex-start;
}
.entry__error {
  margin-top: 0.25rem;
}
.entry__spec {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  font-size: 0.75rem;
  color: var(--lens-graph);
}
.entry__spec li {
  display: flex;
  gap: 0.625rem;
  align-items: baseline;
  font-family: var(--font-mono);
}
.entry__spec .data-mono {
  color: var(--lens-primary);
  width: 3.25rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.625rem;
}
</style>
