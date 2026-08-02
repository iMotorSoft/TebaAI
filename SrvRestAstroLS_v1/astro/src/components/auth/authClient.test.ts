import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchMe } from "./authClient.ts";

const ME_URL = "/api/auth/me";
const TOKEN_KEY = "tebaai_access_token";
const USER_KEY = "tebaai_user";

function setToken(token: string | null): void {
  if (token === null) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token);
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("fetchMe status contract", () => {
  it("returns unauthorized when no token is stored", async () => {
    setToken(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(await fetchMe()).toEqual({ status: "unauthorized" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns the user and persists it for a 200 response", async () => {
    setToken("token");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: "u1", email: "g@example.com", username: null, role: "viewer", is_active: true }, 200),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchMe();
    expect(result).toEqual({ status: "ok", user: expect.objectContaining({ role: "viewer", is_active: true }) });
    expect(fetchMock).toHaveBeenCalledWith(ME_URL, {
      method: "GET",
      headers: { Authorization: "Bearer token" },
    });
    expect(localStorage.getItem(USER_KEY)).toContain("viewer");
  });

  it("maps 401 to unauthorized without redirecting to a user", async () => {
    setToken("token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid token" }, 401)));
    expect(await fetchMe()).toEqual({ status: "unauthorized" });
  });

  it("maps 403 to forbidden", async () => {
    setToken("token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "forbidden" }, 403)));
    expect(await fetchMe()).toEqual({ status: "forbidden" });
  });

  it("maps 5xx responses to error", async () => {
    setToken("token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, 500)));
    expect(await fetchMe()).toEqual({ status: "error" });
  });

  it("maps network failures to error", async () => {
    setToken("token");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect(await fetchMe()).toEqual({ status: "error" });
  });

  it("every branch terminates: ok / unauthorized / forbidden / error cover all statuses", async () => {
    setToken("token");
    const outcomes: string[] = [];
    for (const status of [200, 401, 403, 500, 503]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, status)));
      const result = await fetchMe();
      outcomes.push(result.status);
    }
    expect(outcomes).toEqual(["ok", "unauthorized", "forbidden", "error", "error"]);
  });
});
