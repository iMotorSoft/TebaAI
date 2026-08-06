import { execFileSync } from "node:child_process";
import path from "node:path";
import fs from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";

export const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
export const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";

export const BACKEND = "http://127.0.0.1:7008";
export const E2E_SCOPE = "breslov_e2e";

const BACKEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../backend");
const BACKEND_PYTHON =
  process.env.TEBAAI_BACKEND_PYTHON ?? path.join(BACKEND_DIR, ".venv", "bin", "python");

/** Run a backend script with the project venv; falls back to `uv run python`. */
function runBackend(args: string[], timeoutMs: number): string {
  const env = { ...process.env } as Record<string, string>;
  try {
    return execFileSync(BACKEND_PYTHON, args, { cwd: BACKEND_DIR, env, encoding: "utf-8", timeout: timeoutMs });
  } catch (err) {
    const first = err as { message?: string; stdout?: Buffer; stderr?: Buffer };
    if (process.env.CM_E2E_DEBUG) {
      // eslint-disable-next-line no-console
      console.error(
        `runBackend fallback: ${first.message ?? ""} ${(first.stderr ?? first.stdout ?? "").toString().slice(0, 300)}`,
      );
    }
    return execFileSync("uv", ["run", "python", ...args], { cwd: BACKEND_DIR, env, encoding: "utf-8", timeout: timeoutMs });
  }
}

/**
 * Login as the E2E admin through the real UI and land on /research.
 */
export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.fill("#login-email", ADMIN_EMAIL);
  await page.fill("#login-password", ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.waitForURL(/\/research$/);
}

export async function loginAs(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.waitForURL(/\/research$/);
}

/** Direct API login for the admin credentials; returns the access token. */
export async function apiLogin(): Promise<string> {
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });
  if (!res.ok) throw new Error(`API login failed: ${res.status}`);
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

/** Upload a fixture file into breslov_e2e; returns the upload response. */
export async function apiUpload(
  token: string,
  filePath: string,
  filename = path.basename(filePath),
): Promise<Record<string, unknown>> {
  const form = new FormData();
  form.append(
    "file",
    new Blob([fs.readFileSync(filePath)], { type: "application/pdf" }),
    filename,
  );
  const res = await fetch(`${BACKEND}/admin/content/uploads?knowledge_scope_code=${E2E_SCOPE}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(`upload failed ${res.status}: ${body.detail ?? ""}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

/** Create a job for an upload_id; returns the job response. */
export async function apiCreateJob(
  token: string,
  uploadId: string,
  title: string,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${BACKEND}/admin/content/jobs?knowledge_scope_code=${E2E_SCOPE}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      upload_id: uploadId,
      knowledge_scope_code: E2E_SCOPE,
      title,
      language: "es",
      requested_status: "test_candidate",
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(`create job failed ${res.status}: ${body.detail ?? ""}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

export async function apiCancelJob(token: string, jobId: string): Promise<Record<string, unknown>> {
  const res = await fetch(
    `${BACKEND}/admin/content/jobs/${jobId}/cancel?knowledge_scope_code=${E2E_SCOPE}`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` } },
  );
  if (!res.ok) throw new Error(`cancel failed ${res.status}`);
  return (await res.json()) as Record<string, unknown>;
}

/**
 * Exact manifest cleanup via the official runner. Mirrors the DEV procedure
 * used by the functional E2E: Milvus-first, manifest-bounded, idempotent.
 */
export function runCleanup(jobId: string, attempt = 1): string {
  try {
    return runBackend(
      ["scripts/content_manager_cleanup_job.py", jobId, String(attempt), "--json"],
      90_000,
    );
  } catch (err) {
    const e = err as { stdout?: Buffer; stderr?: Buffer; message?: string };
    return `cleanup error: ${e.message ?? ""} ${(e.stdout ?? e.stderr ?? "").toString().slice(0, 200)}`;
  }
}

/** Generate an authorized fixture variant via the backend script. */
export function generateFixture(
  variant: "v1" | "v2" | "v3" | "v4" | "unique",
  outDir: string,
): string {
  const file = path.join(outDir, `tebaai-cm-e2e-${variant}.pdf`);
  runBackend(
    ["scripts/generate_content_manager_e2e_fixture.py", file, "--variant", variant],
    60_000,
  );
  return file;
}

/**
 * Authorize a fixture sha in the local DEV env (backend-dev.local) and
 * restart backend + worker so the isolated worker accepts it. This is the
 * documented DEV-only E2E enablement path; never touches production config.
 */
export function authorizeFixtureSha(sha256: string): void {
  const envFile = path.resolve(BACKEND_DIR, "../.env.backend-dev.local");
  const env = fs.readFileSync(envFile, "utf-8");
  const updated = env.replace(
    /^TEBAAI_CONTENT_MANAGER_E2E_FIXTURE_SHA256=.*$/m,
    `TEBAAI_CONTENT_MANAGER_E2E_FIXTURE_SHA256=${sha256}`,
  );
  if (updated === env) {
    throw new Error(`E2E_FIXTURE_SHA256 line not found in ${envFile}`);
  }
  fs.writeFileSync(envFile, updated);
}

/** Compute the sha256 of a generated fixture file. */
export function sha256OfFile(filePath: string): string {
  return createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}
