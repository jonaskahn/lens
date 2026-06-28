import type { ToastMessageOptions } from "primevue/toast";

interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

function isFetchError(err: unknown): err is {
  status: number;
  data?: ApiErrorBody;
  headers?: { get: (name: string) => string | null };
} {
  return Boolean(err && typeof err === "object" && "status" in err);
}

export function handleApiError(
  err: unknown,
  toast: { add: (msg: ToastMessageOptions) => void },
): void {
  if (isFetchError(err)) {
    if (err.status === 401) {
      toast.add({
        severity: "error",
        summary: "Unauthorized",
        detail: "Your session has expired. Please log in again.",
        life: 5000,
      });
      const authStore = useAuthStore();
      authStore.clear();
      navigateTo("/login");
      return;
    }

    if (err.status === 403) {
      toast.add({
        severity: "error",
        summary: "Forbidden",
        detail: "You do not have the required permissions.",
        life: 5000,
      });
      return;
    }

    if (err.status === 404) {
      toast.add({
        severity: "warn",
        summary: "Not Available",
        detail: "This feature is not yet available or the endpoint is missing.",
        life: 5000,
      });
      return;
    }

    if (err.status === 429) {
      const retryAfter = err.headers?.get("Retry-After");
      toast.add({
        severity: "warn",
        summary: "Rate Limited",
        detail: retryAfter
          ? `Too many requests. Retry after ${retryAfter}s.`
          : "Too many requests. Please slow down.",
        life: 5000,
      });
      return;
    }

    if (err.status >= 500) {
      toast.add({
        severity: "error",
        summary: "Server Error",
        detail: err.data?.error?.message ?? "The backend returned an internal error.",
        life: 5000,
      });
      return;
    }

    const message = err.data?.error?.message ?? "An unexpected error occurred";
    toast.add({
      severity: "error",
      summary: "Error",
      detail: message,
      life: 5000,
    });
    return;
  }

  toast.add({
    severity: "error",
    summary: "Error",
    detail: "An unexpected error occurred",
    life: 5000,
  });
}
