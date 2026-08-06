import { describe, expect, it } from "vitest";

import { API_BASE_URL } from "./global.js";

describe("frontend API configuration", () => {
  it("always uses the same-origin API proxy", () => {
    expect(API_BASE_URL).toBe("/api");
  });
});
