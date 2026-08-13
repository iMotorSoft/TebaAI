import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAsAdmin } from "./content-manager-helpers";

/**
 * Content Manager — administrative library dashboard.
 *
 * The primary surface is a document library (not a job monitor): summary
 * indicators, real documents with editorial state, and an on-demand detail.
 * Uses the real backend (read-only) — no writes.
 */

test.describe("Content Manager library dashboard (real backend)", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("library shows summary indicators and real documents", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/content");

    // Editorial identity.
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toBeVisible();

    // Summary indicators (document-centric).
    const summary = page.locator(".cm-summary");
    await expect(summary).toBeVisible();
    await expect(summary.getByText("Documentos")).toBeVisible();
    await expect(summary.getByText("Listos")).toBeVisible();
    await expect(summary.getByText("Candidatos para revisión")).toBeVisible();
    await expect(summary.getByText("En procesamiento")).toBeVisible();
    await expect(summary.getByText("Con observaciones")).toBeVisible();
    await expect(summary.getByText("Fallidos")).toBeVisible();

    // The library section lists real documents (the entity is Document, not job).
    await expect(page.getByRole("heading", { name: "Biblioteca" })).toBeVisible();
    await expect(page.locator(".cm-table tbody tr").first()).toBeVisible();

    // The historical real document is present.
    await expect(
      page.getByText("Likutey Halajot — Interior Final").first(),
    ).toBeVisible();
  });

  test("opens a document detail and returns", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/content");

    // Open the first document row.
    const firstRow = page.locator(".cm-table tbody tr").first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();

    // Detail view loads.
    await expect(page.getByRole("button", { name: "← Volver al gestor" })).toBeVisible();

    // Return to the library.
    await page.getByRole("button", { name: "← Volver al gestor" }).click();
    await expect(page.getByRole("heading", { name: "Biblioteca" })).toBeVisible();
  });
});
