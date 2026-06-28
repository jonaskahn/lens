import {
  getSessionSecret,
  getApiBaseUrl,
  sealLensSession,
} from "../../utils/session";
import { randomBytes } from "node:crypto";

const CSRF_COOKIE = "csrf_token";

export default defineEventHandler(async (event) => {
  const body = await readBody<{ api_key: string }>(event);

  if (!body.api_key) {
    throw createError({
      statusCode: 400,
      statusMessage: "api_key is required",
    });
  }

  const baseUrl = getApiBaseUrl();

  try {
    await $fetch<{ items: unknown[] }>(`${baseUrl}/api/v1/domains?limit=1`, {
      headers: { authorization: `Bearer ${body.api_key}` },
    });

    const scopes: string[] = ["read"];

    const writeRes = await $fetch.raw(`${baseUrl}/api/v1/imports`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${body.api_key}`,
        "content-type": "application/json",
      },
      body: "{}",
      ignoreResponseError: true,
    });
    if (writeRes.status !== 401 && writeRes.status !== 403) {
      scopes.push("write");
    }

    const adminRes = await $fetch.raw(`${baseUrl}/api/v1/admin/capabilities`, {
      headers: { authorization: `Bearer ${body.api_key}` },
      ignoreResponseError: true,
    });
    if (adminRes.status !== 401 && adminRes.status !== 403) {
      scopes.push("admin");
    }

    const sessionData = { scopes };

    const secret = getSessionSecret();
    const sealed = await sealLensSession(event, sessionData, secret);

    setCookie(event, "lens_session", sealed, {
      httpOnly: true,
      sameSite: "strict",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24,
    });

    const csrfToken = randomBytes(32).toString("base64url");
    setCookie(event, CSRF_COOKIE, csrfToken, {
      httpOnly: false,
      sameSite: "strict",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24,
    });

    return { scopes };
  } catch (err: unknown) {
    const status = (err as { statusCode?: number }).statusCode;
    if (status === 401 || status === 403) {
      throw createError({
        statusCode: 401,
        statusMessage: "Invalid API key",
      });
    }
    throw createError({
      statusCode: 502,
      statusMessage: "Backend unreachable",
    });
  }
});
