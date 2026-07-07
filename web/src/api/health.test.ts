import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchEngineHealth } from "./health";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchEngineHealth", () => {
  it("parses a successful health response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "ok",
          service: "naijaledger-engine",
          version: "0.1.0",
        }),
      }),
    );

    const health = await fetchEngineHealth();

    expect(health).toEqual({
      status: "ok",
      service: "naijaledger-engine",
      version: "0.1.0",
    });
  });

  it("throws when the API response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
      }),
    );

    await expect(fetchEngineHealth()).rejects.toThrow("HTTP 503");
  });
});
