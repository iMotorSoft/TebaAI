import { test, expect } from "@playwright/test";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  loginAsAdmin,
  apiLogin,
  apiUpload,
  apiCreateJob,
  apiCancelJob,
  runCleanup,
  generateFixture,
  sha256OfFile,
  authorizeFixtureSha,
} from "./content-manager-helpers";

/**
 * Content Manager premium UX — real admin browser flow.
 *
 * No mocks: real backend, isolated worker (breslov_e2e), authorized fixtures.
 * Each test uses a unique fixture sha (fresh idempotency key), authorized in
 * the local DEV env with a backend+worker restart. Never touches production.
 */

const BACKEND = "http://127.0.0.1:7008";
const E2E_SCOPE = "breslov_e2e";

async function prepareFixture(): Promise<string> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "cm-e2e-"));
  const fixturePath = generateFixture("unique", dir);
  const sha = sha256OfFile(fixturePath);
  authorizeFixtureSha(sha);
  execFileSync(path.resolve(process.cwd(), "../backend-dev.sh"), ["restart"], {
    cwd: path.resolve(process.cwd(), ".."),
    encoding: "utf-8",
    timeout: 90_000,
  });
  execFileSync(path.resolve(process.cwd(), "../content-worker-dev.sh"), ["restart"], {
    cwd: path.resolve(process.cwd(), ".."),
    encoding: "utf-8",
    timeout: 90_000,
  });
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`${BACKEND}/health`);
      if (res.ok) return fixturePath;
    } catch {
      /* not ready yet */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("backend did not become healthy");
}

async function waitTerminal(jobId: string, token: string, timeoutMs = 120_000): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(`${BACKEND}/admin/content/jobs/${jobId}?knowledge_scope_code=${E2E_SCOPE}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = (await res.json()) as { status: string };
    if (["completed", "completed_with_warnings", "failed", "cancelled"].includes(body.status)) {
      return body.status;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("job did not reach terminal state");
}

test.describe("Content Manager premium UX (real backend)", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("five-stage wizard completes with real counts and diagnostic", async ({ page }) => {
    const fixturePath = await prepareFixture();

    await loginAsAdmin(page);
    await page.goto("/admin/content");

    // ── Editorial identity, not a generic admin shell ───────────────────
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toBeVisible();
    await expect(page.getByText("Carga, procesamiento y validación de fuentes documentales")).toBeVisible();
    await expect(page.getByText("רבי נחמן")).toBeVisible();
    await expect(page.getByText(/REBE NAJMÁN · BRESLOV RESEARCH/)).toBeVisible();

    // ── Step 1 · Archivo ────────────────────────────────────────────────
    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    await expect(page.getByText("Seleccioná una fuente documental")).toBeVisible();
    await expect(page.getByText(/PDF de hasta/)).toBeVisible();

    await page.locator("#cm-file-input").setInputFiles(fixturePath);

    await expect(page.locator(".cm-file-name")).toContainText("tebaai-cm-e2e-unique.pdf");
    await expect(page.getByText("Archivo válido")).toBeVisible();
    await expect(page.getByText("3 páginas")).toBeVisible();

    const technical = page.locator("details.cm-details");
    await expect(technical.locator("summary")).toHaveText(/Detalles técnicos/);
    await expect(technical).not.toHaveAttribute("open", "");

    // ── Step 2 · Información ────────────────────────────────────────────
    await page.getByRole("button", { name: "Continuar" }).click();
    await expect(page.getByLabel("Título de la obra")).toBeVisible();
    await page.getByLabel("Título de la obra").fill("Fuente Premium UX Playwright");
    await page.getByLabel("Idioma principal").selectOption("mixed");
    await page.getByLabel("Familia documental (opcional)").fill("Likutey Moharan");
    await page.getByRole("button", { name: "Continuar a confirmación" }).click();

    // ── Step 3 · Confirmación ───────────────────────────────────────────
    await expect(page.getByRole("heading", { name: "Confirmación" })).toBeVisible();
    await expect(page.getByText("El documento será procesado y quedará como candidato para revisión.")).toBeVisible();
    await expect(page.getByText("Esta operación no publica ni aprueba el documento.")).toBeVisible();
    await expect(page.getByText("Fuente Premium UX Playwright")).toBeVisible();

    // ── Step 4 · Procesamiento (real) ───────────────────────────────────
    const createResponse = page.waitForResponse(
      (res) => res.url().includes("/admin/content/jobs") && res.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Iniciar procesamiento" }).click();
    const created = await createResponse;
    const createdBody = (await created.json()) as { job_id: string; status: string };
    expect(createdBody.status).toBe("queued");
    const jobId = createdBody.job_id;

    await expect(page.getByRole("heading", { name: "Procesando el documento" })).toBeVisible();
    await expect(page.getByText(/Podés salir de esta pantalla/)).toBeVisible();

    // Observe real stage progression (not a single spinner)
    await expect(page.locator(".cm-stage[data-state='done']").first()).toBeVisible({ timeout: 30_000 });

    // ── Step 5 · Resultado (real terminal state) ────────────────────────
    await expect(page.getByRole("heading", { name: /Documento procesado/ })).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText("Candidato para revisión").first()).toBeVisible();
    await expect(page.locator(".cm-stat").first()).toBeVisible();
    const stats = await page.locator(".cm-stat strong").allTextContents();
    expect(stats.length).toBeGreaterThanOrEqual(4);
    await expect(page.getByRole("button", { name: "Abrir diagnóstico" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Probar en Investigación" })).toBeVisible();
    await expect(page.getByText("Este documento todavía no fue aprobado.")).toBeVisible();
    await expect(page.getByText(/Publicar|Aprobar|producción/i)).toHaveCount(0);

    // ── Diagnostic (collapsed by default, expands on request) ──────────
    await page.getByRole("button", { name: "Abrir diagnóstico" }).click();
    await expect(page.getByText("Detalle del documento")).toBeVisible({ timeout: 15_000 });
    const diagnostic = page.locator("details.cm-details");
    await expect(diagnostic.locator("summary")).toHaveText(/Diagnóstico técnico/);
    await expect(diagnostic).not.toHaveAttribute("open", "");
    await diagnostic.locator("summary").click();
    await expect(diagnostic).toHaveAttribute("open", "");
    await expect(diagnostic.getByText("Páginas PDF")).toBeVisible();
    await expect(diagnostic.getByText("Fragmentos")).toBeVisible();
    await expect(diagnostic.getByText("Registros de búsqueda")).toBeVisible();
    await expect(diagnostic.getByText("PG ↔ Milvus")).toBeVisible();

    // ── History ─────────────────────────────────────────────────────────
    await page.getByRole("button", { name: "← Volver al gestor" }).click();
    await expect(page.getByRole("heading", { name: "Biblioteca" })).toBeVisible();
    // The E2E document is hidden by default; enable test data to see it.
    await page.getByLabel("Mostrar datos de prueba").check();
    await expect(page.getByText("Fuente Premium UX Playwright").first()).toBeVisible();

    // ── Exact duplicate (same fixture again) ────────────────────────────
    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    await page.locator("#cm-file-input").setInputFiles(fixturePath);
    await expect(page.getByText("Este mismo archivo ya fue cargado.")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Documento existente:/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Continuar" })).toHaveCount(0);

    // ── Cleanup exact (manifest) ────────────────────────────────────────
    const token = await apiLogin();
    await waitTerminal(jobId, token);
    const cleanupOut = runCleanup(jobId, 1);
    expect(cleanupOut).toContain("completed");

    // ── Logout ──────────────────────────────────────────────────────────
    await page.goto("/admin/content");
    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    await page.waitForURL(/\/login/);
  });

  test("cancelled job retries with a new attempt and completes", async ({ page }) => {
    const fixturePath = await prepareFixture();
    const token = await apiLogin();

    // Create and cancel in a burst before the ~1s worker poll
    const upload = await apiUpload(token, fixturePath);
    const job = await apiCreateJob(token, String(upload.upload_id), "Fuente Retry Playwright");
    const jobId = String(job.job_id);
    const cancelled = await apiCancelJob(token, jobId);
    expect(cancelled.status).toBe("cancelled");

    await loginAsAdmin(page);
    await page.goto("/admin/content");
    // The cancelled E2E job is hidden by default; enable test data.
    await page.getByLabel("Mostrar datos de prueba").check();

    const row = page.locator(".cm-table tbody tr", { hasText: "Fuente Retry Playwright" }).filter({ hasText: "Cancelado" }).first();
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Abrir" }).click();
    await expect(page.getByText("El procesamiento fue cancelado antes de iniciar las escrituras.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Reintentar" })).toBeVisible();

    // Real retry → new attempt → worker processes → terminal
    await page.getByRole("button", { name: "Reintentar" }).click();
    await expect(page.getByText("En procesamiento").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".cm-detail-head .cm-status")).toContainText(/Con observaciones|Candidato para revisión/, {
      timeout: 120_000,
    });
    await expect(page.locator(".cm-detail-head .cm-sub")).toContainText("intento 2");

    // Cleanup of the retried attempt (manifest-bounded). The retry created a
    // NEW job id; the cancelled original has no manifest to compensate.
    const jobsRes = await fetch(`${BACKEND}/admin/content/jobs?knowledge_scope_code=${E2E_SCOPE}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const jobsBody = (await jobsRes.json()) as {
      jobs: Array<{ job_id: string; title: string; attempt_number: number; status: string }>;
    };
    const attempt2 = jobsBody.jobs.find(
      (j) => j.title === "Fuente Retry Playwright" && j.attempt_number === 2,
    );
    expect(attempt2).toBeTruthy();
    expect(["completed", "completed_with_warnings"]).toContain(attempt2!.status);
    const cleanupOut = runCleanup(attempt2!.job_id, 2);
    expect(cleanupOut).toContain("completed");
  });
});

/** Permissions: route and API must deny non-admin sessions. */
test.describe("Content Manager permissions", () => {
  test("admin route redirects to login without a session", async ({ page }) => {
    await page.goto("/admin/content");
    await expect(page).toHaveURL(/\/login/);
  });

  test("invalid token never shows the manager table", async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => {
      localStorage.setItem("tebaai_access_token", "invalid-token");
      localStorage.setItem("tebaai_refresh_token", "invalid-token");
      localStorage.setItem("tebaai_user", JSON.stringify({ role: "viewer", email: "viewer@tebaai.local" }));
    });
    await page.goto("/admin/content");
    await expect(page.locator(".cm-table")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toHaveCount(0);
  });
});
