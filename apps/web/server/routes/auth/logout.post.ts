export default defineEventHandler(async (event) => {
  const cookieOpts = {
    httpOnly: true,
    sameSite: "strict" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
  };

  deleteCookie(event, "lens_session", cookieOpts);
  deleteCookie(event, "csrf_token", {
    ...cookieOpts,
    httpOnly: false,
  });

  return { success: true };
});
