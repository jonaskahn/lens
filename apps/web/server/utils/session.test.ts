import { describe, it, expect, vi } from "vitest";

vi.stubGlobal("createError", vi.fn((opts: { statusCode: number; statusMessage: string }) => {
  const err = new Error(opts.statusMessage) as Error & { statusCode: number };
  err.statusCode = opts.statusCode;
  throw err;
}));

const { sealLensSession, unsealLensSession } = await import("./session");

const SECRET = "a-very-secure-password-at-least-32-chars!!";

describe("session seal/unseal", () => {
  const sessionData = { scopes: ["read", "write"], username: "test-user" };

  it("roundtrip preserves session data", async () => {
    const sealed = await sealLensSession(null, sessionData, SECRET);
    const unsealed = await unsealLensSession(null, sealed, SECRET);
    expect(unsealed).toEqual(sessionData);
  });

  it("roundtrip with admin scopes", async () => {
    const data = { scopes: ["read", "write", "admin"] };
    const sealed = await sealLensSession(null, data, SECRET);
    const unsealed = await unsealLensSession(null, sealed, SECRET);
    expect(unsealed?.scopes).toEqual(["read", "write", "admin"]);
  });

  it("roundtrip without username", async () => {
    const data = { scopes: ["read"] };
    const sealed = await sealLensSession(null, data, SECRET);
    const unsealed = await unsealLensSession(null, sealed, SECRET);
    expect(unsealed).toEqual(data);
    expect(unsealed?.username).toBeUndefined();
  });

  it("rejects tampered sealed data", async () => {
    const sealed = await sealLensSession(null, sessionData, SECRET);
    const tampered = sealed.slice(0, -8) + "xxxxxxxx";
    const result = await unsealLensSession(null, tampered, SECRET);
    expect(result).toBeNull();
  });

  it("rejects sealed data with wrong secret", async () => {
    const sealed = await sealLensSession(null, sessionData, SECRET);
    const result = await unsealLensSession(
      null,
      sealed,
      "different-wrong-secret-key-that-is-long-enough",
    );
    expect(result).toBeNull();
  });

  it("rejects empty sealed input", async () => {
    const result = await unsealLensSession(null, "", SECRET);
    expect(result).toBeNull();
  });

  it("rejects malformed sealed input", async () => {
    const result = await unsealLensSession(null, "!!!not-valid-base64!!!", SECRET);
    expect(result).toBeNull();
  });

  it("rejects sealed data with short secret", async () => {
    const sealed = await sealLensSession(null, sessionData, SECRET);
    const result = await unsealLensSession(null, sealed, "short");
    expect(result).toBeNull();
  });

  it("produces different output for different data", async () => {
    const a = await sealLensSession(null, { scopes: ["read"] }, SECRET);
    const b = await sealLensSession(null, { scopes: ["write"] }, SECRET);
    expect(a).not.toBe(b);
  });

  it("produces different output for different secrets", async () => {
    const a = await sealLensSession(null, sessionData, SECRET);
    const b = await sealLensSession(
      null,
      sessionData,
      "another-valid-secret-that-is-also-long-enough!",
    );
    expect(a).not.toBe(b);
  });

  it("sealed data does not contain plaintext scopes", async () => {
    const sealed = await sealLensSession(null, sessionData, SECRET);
    expect(sealed).not.toContain("read");
    expect(sealed).not.toContain("write");
    expect(sealed).not.toContain("admin");
    expect(sealed).not.toContain("test-user");
  });
});
