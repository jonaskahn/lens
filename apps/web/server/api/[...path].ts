import {
  getApiBaseUrl,
  getApiKey,
  getLensSession,
} from "../utils/session";

const CSRF_HEADER = "x-csrf-token";
const CSRF_COOKIE = "csrf_token";

function getRequiredScope(method: string, path: string): string {
  if (path.startsWith("/admin")) return "admin";
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) return "write";
  return "read";
}

async function checkCsrf(event: { headers: { get: (name: string) => string | null } }) {
  const { getCookie } = await import("h3");
  const cookieToken = getCookie(event as Parameters<typeof getCookie>[0], CSRF_COOKIE);
  const headerToken = event.headers.get(CSRF_HEADER);

  if (!cookieToken || !headerToken || cookieToken !== headerToken) {
    throw createError({
      statusCode: 403,
      statusMessage: "CSRF token missing or mismatch",
    });
  }
}

export default defineEventHandler(async (event) => {
  const session = await getLensSession(event);
  if (!session) {
    throw createError({
      statusCode: 401,
      statusMessage: "Authentication required",
    });
  }

  const requestUrl = getRequestURL(event);
  const apiPath = requestUrl.pathname;
  const method = event.method.toUpperCase();

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    await checkCsrf(event);
  }

  const requiredScope = getRequiredScope(method, apiPath);
  if (!session.scopes.includes(requiredScope)) {
    throw createError({
      statusCode: 403,
      statusMessage: `Missing required scope: ${requiredScope}`,
    });
  }

  const baseUrl = getApiBaseUrl();
  const apiKey = getApiKey();

  const targetUrl = `${baseUrl}${apiPath}${requestUrl.search}`;

  return proxyRequest(event, targetUrl, {
    headers: {
      authorization: `Bearer ${apiKey}`,
    },
  });
});
