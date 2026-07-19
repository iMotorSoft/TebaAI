import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";

test.describe("Login session recovery", () => {
  test("session card shows with valid session and buttons are functional", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

    const errors: string[] = [];
    page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
    page.on("pageerror", (err) => errors.push(err.message));

    // 1. Login
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research$/);
    await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 15000 });

    // 2. Navigate to /login with active session — session card should appear
    await page.goto("/login");
    await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(ADMIN_EMAIL)).toBeVisible();

    // 3. "Ir a Investigación" is a real link and navigates
    const link = page.getByRole("link", { name: "Ir a Investigación" });
    await expect(link).toHaveAttribute("href", "/research");
    const tagName = await link.evaluate((el) => el.tagName.toLowerCase());
    expect(tagName).toBe("a");
    await link.click();
    await expect(page).toHaveURL(/\/research$/);

    // 4. Return to /login and verify session
    await page.goto("/login");
    await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "Verificar sesión" }).click();
    await expect(page.getByText("Sesión válida.")).toBeVisible({ timeout: 10000 });

    // 5. Cerrar sesión
    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    await expect(page.locator("#login-email")).toBeVisible({ timeout: 10000 });

    // 6. /research redirects to /login after logout
    await page.goto("/research");
    await expect(page).toHaveURL(/\/login$/);

    // 7. No console errors
    expect(errors.length).toBe(0);
  });

  test("research link is a real HTML anchor", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research$/);

    // Navigate to /login to see the session card with the link
    await page.goto("/login");
    await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });

    const link = page.getByRole("link", { name: "Ir a Investigación" });
    await expect(link).toHaveAttribute("href", "/research");
    const tagName = await link.evaluate((el) => el.tagName.toLowerCase());
    expect(tagName).toBe("a");
  });

  test("full flow: login → research → login → verify → logout → re-login", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

    const errors: string[] = [];
    page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
    page.on("pageerror", (err) => errors.push(err.message));

    // 1. Login
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research$/);
    await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 15000 });

    // 2. Navigate to /login — should see session card
    await page.goto("/login");
    await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });

    // 3. Click "Ir a Investigación"
    await page.getByRole("link", { name: "Ir a Investigación" }).click();
    await expect(page).toHaveURL(/\/research$/);

    // 4. Back to /login
    await page.goto("/login");
    await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });

    // 5. Verify session
    await page.getByRole("button", { name: "Verificar sesión" }).click();
    await expect(page.getByText("Sesión válida.")).toBeVisible({ timeout: 10000 });

    // 6. Logout
    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    await expect(page.locator("#login-email")).toBeVisible({ timeout: 10000 });

    // 7. /research redirects to /login
    await page.goto("/research");
    await expect(page).toHaveURL(/\/login$/);

    // 8. Re-login
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research$/);
    await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 15000 });

    expect(errors.length).toBe(0);
  });
});
