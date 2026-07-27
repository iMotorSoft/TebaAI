import { describe, expect, it } from "vitest";

import { API_BASE_URL } from "./global.js";

describe("manual DEV/PRO frontend configuration", () => {
  it("keeps the tracked configuration in DEV mode", () => {
    expect(API_BASE_URL).toBe("http://127.0.0.1:7008");
  });
});
