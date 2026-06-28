import { randomBytes } from "node:crypto";

const CSRF_COOKIE = "csrf_token";

export default defineEventHandler(async (event) => {
  const { getCookie, setCookie } = await import("h3");
  const existing = getCookie(event, CSRF_COOKIE);
  if (!existing) {
    const token = randomBytes(32).toString("base64url");
    setCookie(event, CSRF_COOKIE, token, {
      httpOnly: false,
      sameSite: "strict",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24,
    });
  }
});
