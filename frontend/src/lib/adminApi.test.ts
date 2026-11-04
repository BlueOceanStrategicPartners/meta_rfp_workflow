import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminApiError, AdminAuthError, getOverview, getQuoteExplanation, listRfps } from "./adminApi";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("adminApi", () => {
  it("throws AdminAuthError on 401 (after the refresh attempt fails)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(401, { detail: "Not signed in" })));
    await expect(getOverview()).rejects.toBeInstanceOf(AdminAuthError);
  });

  it("throws AdminAuthError on 403", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(403, { detail: "Forbidden" })));
    const err = await getOverview().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(AdminAuthError);
    expect((err as AdminAuthError).status).toBe(403);
  });

  it("parses detail, errors and alternatives into AdminApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(400, { detail: "Over capacity.", errors: { headcount: ["Too many"] }, alternatives: ["a", "b"] }),
      ),
    );
    const err = (await getOverview().catch((e: unknown) => e)) as AdminApiError;
    expect(err).toBeInstanceOf(AdminApiError);
    expect(err.status).toBe(400);
    expect(err.detail).toBe("Over capacity.");
    expect(err.message).toBe("Over capacity.");
    expect(err.errors).toEqual({ headcount: ["Too many"] });
    expect(err.alternatives).toEqual(["a", "b"]);
  });

  it("uses a plain message when the error body has no detail", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("oops", { status: 500 })));
    const err = (await getOverview().catch((e: unknown) => e)) as AdminApiError;
    expect(err).toBeInstanceOf(AdminApiError);
    expect(err.detail).toMatch(/server had a problem/i);
  });

  it("builds query strings and skips empty params", async () => {
    const fetchMock = vi.fn(async (_url: string) => jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);
    await listRfps({ status: "NEGOTIATING", q: "" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin-center/rfps/?status=NEGOTIATING");
  });

  it("fetches a quote explanation from its own route", async () => {
    const fetchMock = vi.fn(async (_url: string) => jsonResponse(200, { quote_id: "q-1", steps: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const exp = await getQuoteExplanation("q-1");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin-center/pricing/quotes/q-1/explanation/");
    expect(exp.quote_id).toBe("q-1");
  });
});
