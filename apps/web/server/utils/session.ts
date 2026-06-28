import { seal, unseal, defaults } from "iron-webcrypto";

const SESSION_TTL_SECONDS = 60 * 60 * 24;

function getConfig() {
  return useRuntimeConfig();
}

export function getSessionSecret(): string {
  const config = getConfig();
  if (!config.sessionPassword || config.sessionPassword.length < 32) {
    throw createError({
      statusCode: 500,
      statusMessage: "NUXT_SESSION_PASSWORD must be at least 32 characters",
    });
  }
  return config.sessionPassword;
}

export function getApiKey(): string {
  const config = getConfig();
  if (!config.apiKey) {
    throw createError({
      statusCode: 500,
      statusMessage: "NUXT_API_KEY is not configured",
    });
  }
  return config.apiKey;
}

export function getApiBaseUrl(): string {
  const config = getConfig();
  if (!config.apiBaseUrl) {
    throw createError({
      statusCode: 500,
      statusMessage: "NUXT_API_BASE_URL is not configured",
    });
  }
  return config.apiBaseUrl;
}

export interface SessionData {
  scopes: string[];
  username?: string;
}

export async function sealLensSession(
  _event: unknown,
  data: SessionData,
  secret: string,
): Promise<string> {
  return seal(data, secret, {
    ...defaults,
    ttl: SESSION_TTL_SECONDS * 1000,
  });
}

export async function unsealLensSession(
  _event: unknown,
  sealed: string,
  secret: string,
): Promise<SessionData | null> {
  try {
    const data = await unseal(sealed, secret, {
      ...defaults,
      ttl: SESSION_TTL_SECONDS * 1000,
    });
    return data as SessionData;
  } catch {
    return null;
  }
}

export async function getLensSession(event: unknown): Promise<SessionData | null> {
  const { getCookie } = await import("h3");
  const cookie = getCookie(event as never, "lens_session");
  if (!cookie) return null;
  const secret = getSessionSecret();
  return unsealLensSession(event, cookie, secret);
}
