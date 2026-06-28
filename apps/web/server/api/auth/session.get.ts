import { getLensSession } from "../../utils/session";

export default defineEventHandler(async (event) => {
  const session = await getLensSession(event);
  if (!session) {
    throw createError({
      statusCode: 401,
      statusMessage: "Not authenticated",
    });
  }
  return { scopes: session.scopes, username: session.username };
});
