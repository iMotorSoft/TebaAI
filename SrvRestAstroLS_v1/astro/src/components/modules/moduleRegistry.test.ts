import { describe, it, expect } from "vitest";
import {
  MODULES,
  DEFAULT_POST_LOGIN_DESTINATION,
  resolveSafePostLoginDestination,
  findModuleByDestination,
  roleCanAccessModule,
} from "./moduleRegistry.ts";

describe("module registry", () => {
  it("exposes exactly the enabled modules: Investigación and Edición", () => {
    const ids = MODULES.map((m) => m.id);
    expect(ids).toEqual(["research", "edition"]);
  });

  it("does not expose Administración yet", () => {
    expect(MODULES.some((m) => m.id === "administration")).toBe(false);
  });

  it("defines research for any authenticated user and edition for admin/editor", () => {
    const research = findModuleByDestination("/research");
    const edition = findModuleByDestination("/admin/content");
    expect(research?.requiredRoles).toBeNull();
    expect(edition?.requiredRoles).toEqual(["admin", "editor"]);
  });

  it("resolves each module destination via findModuleByDestination", () => {
    expect(findModuleByDestination("/research")?.label).toBe("Investigación");
    expect(findModuleByDestination("/admin/content")?.label).toBe("Edición");
    expect(findModuleByDestination("/nope")).toBeUndefined();
  });
});

describe("resolveSafePostLoginDestination", () => {
  it("accepts the two V1 destinations exactly", () => {
    expect(resolveSafePostLoginDestination("/research")).toBe("/research");
    expect(resolveSafePostLoginDestination("/admin/content")).toBe("/admin/content");
  });

  it("falls back on empty or null input", () => {
    expect(resolveSafePostLoginDestination(null)).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination(undefined)).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("   ")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });

  it("rejects unknown destinations", () => {
    expect(resolveSafePostLoginDestination("/unknown")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("/admin/users")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });

  it("rejects absolute external URLs", () => {
    expect(resolveSafePostLoginDestination("https://evil.example")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("http://evil.example/path")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });

  it("rejects protocol-relative URLs", () => {
    expect(resolveSafePostLoginDestination("//evil.example")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("//evil.example/research")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });

  it("rejects scheme-based URLs", () => {
    expect(resolveSafePostLoginDestination("javascript:alert(1)")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("data:text/html,x")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("ftp://evil.example")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });

  it("rejects backslash tricks", () => {
    expect(resolveSafePostLoginDestination("/\\evil")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("/admin\\..")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });

  it("strips query string and fragment before matching", () => {
    expect(resolveSafePostLoginDestination("/research?x=1")).toBe("/research");
    expect(resolveSafePostLoginDestination("/admin/content#section")).toBe("/admin/content");
  });

  it("rejects encoded malicious URLs after decoding", () => {
    // URLSearchParams already decodes `%2F%2Fevil.example` to `//evil.example`.
    expect(resolveSafePostLoginDestination("//evil.example")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
    expect(resolveSafePostLoginDestination("https://evil.example")).toBe(DEFAULT_POST_LOGIN_DESTINATION);
  });
});

describe("roleCanAccessModule", () => {
  it("allows any authenticated role into research", () => {
    const research = findModuleByDestination("/research")!;
    expect(roleCanAccessModule("admin", research)).toBe(true);
    expect(roleCanAccessModule("editor", research)).toBe(true);
    expect(roleCanAccessModule("viewer", research)).toBe(true);
  });

  it("allows only admin/editor into edition", () => {
    const edition = findModuleByDestination("/admin/content")!;
    expect(roleCanAccessModule("admin", edition)).toBe(true);
    expect(roleCanAccessModule("editor", edition)).toBe(true);
    expect(roleCanAccessModule("viewer", edition)).toBe(false);
  });
});
