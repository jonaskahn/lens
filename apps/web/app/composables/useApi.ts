import createClient from "openapi-fetch";

import type { paths } from "~/types/api";

interface FetchOptions {
  query?: Record<string, unknown>;
  body?: unknown;
  headers?: Record<string, string>;
  path?: Record<string, string>;
}

function getCsrfToken(): string {
  if (import.meta.client) {
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    return match?.[1] ?? "";
  }
  return "";
}

function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const csrf = getCsrfToken();
  if (!csrf) return extra ?? {};
  return { "x-csrf-token": csrf, ...extra };
}

function resolveUrl(path: string, pathParams?: Record<string, string>): string {
  let url = path;
  if (pathParams) {
    for (const [key, value] of Object.entries(pathParams)) {
      url = url.replace(`{${key}}`, encodeURIComponent(value));
    }
  }
  return url;
}

const rawClient = createClient<paths>({
  baseUrl: "",
  credentials: "same-origin",
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const client = rawClient as any;

async function request(method: string, path: string, options?: FetchOptions) {
  const url = resolveUrl(path, options?.path);
  const fetchOpts = {
    params: { query: options?.query },
    body: options?.body,
    headers: buildHeaders(options?.headers),
  };

  let result;
  switch (method) {
    case "GET":
      result = await client.GET(url, fetchOpts);
      break;
    case "POST":
      result = await client.POST(url, fetchOpts);
      break;
    case "PUT":
      result = await client.PUT(url, fetchOpts);
      break;
    case "PATCH":
      result = await client.PATCH(url, fetchOpts);
      break;
    case "DELETE":
      result = await client.DELETE(url, fetchOpts);
      break;
    default:
      throw new Error(`Unknown method: ${method}`);
  }

  if (result.error) throw result.error;
  return result.data;
}

export function useApi() {
  return {
    get: <T>(path: string, options?: FetchOptions) => request("GET", path, options) as Promise<T>,
    post: <T>(path: string, options?: FetchOptions) => request("POST", path, options) as Promise<T>,
    put: <T>(path: string, options?: FetchOptions) => request("PUT", path, options) as Promise<T>,
    patch: <T>(path: string, options?: FetchOptions) => request("PATCH", path, options) as Promise<T>,
    del: <T>(path: string, options?: FetchOptions) => request("DELETE", path, options) as Promise<T>,
  };
}
