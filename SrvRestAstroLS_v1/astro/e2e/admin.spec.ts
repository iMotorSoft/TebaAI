import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "admin@tebaai.ai";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "Admin123!";

test.describe("Admin users UI", () => {
  test("redirects to login when not authenticated", async ({ page }) => {
    await page.goto("/admin/users");
    await expect(page.locator("text=Debes iniciar sesión")).toBeVisible();
    await expect(page.getByRole("link", { name: "Iniciar sesión" })).toBeVisible();
  });

  test("admin can list users", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });

    await page.goto("/admin/users");
    await expect(page.locator("text=Administración de usuarios")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("table")).toBeVisible();
  });

  test("admin can create a user", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });

    await page.goto("/admin/users");
    await expect(page.locator("text=Administración de usuarios")).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: "Crear usuario" }).click();
    const ts = String(Date.now());
    await page.fill("input[type=email]", `viewer.e2e+${ts}@tebaai.local`);
    await page.fill("input[type=text]", `viewer_e2e_${ts}`);
    await page.fill("input[type=password]", "ViewerE2e123!");
    await page.getByRole("button", { name: "Crear" }).click();

    await expect(page.locator(".alert-success")).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("cell", { name: `viewer.e2e+${ts}@tebaai.local` })).toBeVisible();
  });

  test("admin can deactivate and reactivate a user", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });

    await page.goto("/admin/users");
    await expect(page.locator("text=Administración de usuarios")).toBeVisible({ timeout: 10000 });

    // Wait for table to have rows
    await expect(page.locator("table tbody tr")).not.toHaveCount(0, { timeout: 15000 });

    // Find a row with "Activo" badge (active user that is NOT the admin)
    const rows = page.locator("table tbody tr");
    const rowCount = await rows.count();

    let deactivatedEmail = "";
    for (let i = 0; i < rowCount; i++) {
      const row = rows.nth(i);
      const roleBadge = row.locator("td").nth(2);
      const statusBadge = row.locator("td").nth(3);
      const roleText = await roleBadge.textContent();
      const statusText = await statusBadge.textContent();

      if (statusText?.trim() === "Activo" && roleText?.trim() !== "admin") {
        // Get email from first td
        deactivatedEmail = (await row.locator("td").nth(0).textContent()) || "";
        // Click deactivate
        await row.locator("button:has-text('Desactivar')").click();
        break;
      }
    }

    expect(deactivatedEmail).toBeTruthy();
    await expect(page.locator(`text=Usuario ${deactivatedEmail} desactivado`)).toBeVisible({ timeout: 10000 });

    // Reactivate the same user
    for (let i = 0; i < rowCount; i++) {
      const row = rows.nth(i);
      const emailCell = await row.locator("td").nth(0).textContent();
      if (emailCell?.trim() === deactivatedEmail) {
        await row.locator("button:has-text('Activar')").click();
        break;
      }
    }
    await expect(page.locator(`text=Usuario ${deactivatedEmail} activado`)).toBeVisible({ timeout: 10000 });
  });
});
