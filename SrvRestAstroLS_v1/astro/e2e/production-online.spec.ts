import { expect, test, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "";
const adminEmail = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const adminPassword = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const secondAdminEmail = process.env.TEBAAI_E2E_ADMIN_2_EMAIL ?? "";
const secondAdminPassword = process.env.TEBAAI_E2E_ADMIN_2_PASSWORD ?? "";
const guestPassword = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const isProductionTarget = baseURL === "https://breslov.tebaai.live";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/research\/?$/);
  await expect(page.getByTestId("research-question")).toBeVisible();
}

async function logout(page: Page) {
  await page.locator("button:visible").filter({ hasText: "Cerrar sesión" }).first().click();
  await expect(page).toHaveURL(/\/login\/?$/);
}

async function ask(page: Page, question: string) {
  const responsePromise = page.waitForResponse((response) => {
    if (!response.url().endsWith("/library/investigative-qa/v1")) return false;
    if (response.request().method() !== "POST") return false;
    return response.request().postDataJSON()?.phase === "analyze";
  }, { timeout: 180_000 });

  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-analyze")).toBeVisible();
  await page.getByTestId("interpretation-analyze").click();

  const response = await responsePromise;
  const body = await response.json();
  expect(response.status()).toBe(200);
  expect(body.status).toBe("ok");
  expect(body.answer_text?.trim()).toBeTruthy();
  expect(body.hits?.length).toBeGreaterThan(0);
  expect(body.primary_evidence_ids?.length).toBeGreaterThan(0);
  expect(body.claims?.length).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: "Fuentes del turno" })).toBeVisible();
  await expect(page.locator(".source-list button:visible").first()).toBeVisible();
}

test.describe("public production closure", () => {
  test.skip(!isProductionTarget, "requires the canonical HTTPS production target");

  test("both administrators authenticate, reach administration, reject a wrong password and log out", async ({ page }) => {
    test.setTimeout(120_000);
    test.skip(
      !adminEmail || !adminPassword || !secondAdminEmail || !secondAdminPassword,
      "requires both production administrator credentials",
    );

    await page.goto("/login");
    await page.locator("#login-email").fill(adminEmail);
    await page.locator("#login-password").fill(`${adminPassword}-incorrect`);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator('[role="alert"]')).toBeVisible();

    for (const [email, password] of [
      [adminEmail, adminPassword],
      [secondAdminEmail, secondAdminPassword],
    ]) {
      await login(page, email, password);
      await page.goto("/admin/users");
      await expect(page.getByText("Administración de usuarios")).toBeVisible();
      await expect(page.locator("table")).toBeVisible();
      await page.goto("/research");
      await expect(page.getByTestId("research-question")).toBeVisible();
      await logout(page);
    }
  });

  test("Spanish, English and Hebrew research stays grounded on desktop and mobile", async ({ page }) => {
    test.setTimeout(300_000);
    test.skip(!adminEmail || !adminPassword, "requires production administrator credentials");
    await login(page, adminEmail, adminPassword);

    const questions = [
      "¿En qué partes se habla de la tristeza y cuáles son las fuentes?",
      "Where is fear discussed and what are the cited sources?",
      "איפה מופיע המושג עקרב",
    ];

    for (const [index, question] of questions.entries()) {
      await ask(page, question);
      if (index < questions.length - 1) {
        await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
      }
    }

    await expect(page.locator(".user-turn h2").last()).toHaveText(questions.at(-1)!);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.setViewportSize({ width: 1366, height: 768 });
    await logout(page);
  });

  test("guest researches with sources but cannot read or write administrative users", async ({ page }) => {
    test.setTimeout(180_000);
    test.skip(!guestPassword, "requires the production guest credential");
    await login(page, "guest@tebaai.live", guestPassword);
    await ask(page, "¿En qué partes se habla de la tristeza y cuáles son las fuentes?");

    const statuses = await page.evaluate(async () => {
      const token = localStorage.getItem("tebaai_access_token");
      const headers = {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };
      const read = await fetch("/api/users", { headers });
      const write = await fetch("/api/users", {
        method: "POST",
        headers,
        body: JSON.stringify({
          email: "forbidden-probe@tebaai.local",
          username: "forbidden_probe",
          password: "NotARealCredential123!",
          role: "viewer",
          is_active: true,
        }),
      });
      return [read.status, write.status];
    });
    expect(statuses).toEqual([403, 403]);

    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await logout(page);
  });
});
