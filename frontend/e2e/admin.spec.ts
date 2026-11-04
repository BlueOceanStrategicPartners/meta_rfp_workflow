import { expect, test, type Page } from "@playwright/test";

// Needs both servers running and the demo accounts seeded (seed_admin_demo).
const ADMIN = { email: "admin@demo.local", password: "admin12345" };
const DESIGNER = { email: "designer@demo.local", password: "demo12345" };

async function signIn(page: Page, who: { email: string; password: string }) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.locator('input[type="email"]').fill(who.email);
  await page.locator('input[type="password"]').fill(who.password);
  await page.getByRole("button", { name: /sign in with email/i }).click();
}

test("unauthenticated /admin redirects to unified sign-in", async ({ page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("designer account opens the designer portal, not admin", async ({ page }) => {
  await signIn(page, DESIGNER);
  await expect(page).toHaveURL(/\/designer$/);
  await page.goto("/admin");
  await expect(page.getByRole("navigation", { name: "Admin modules" })).toHaveCount(0);
});

test("demo admin signs in and can visit every module from the rail", async ({ page }) => {
  await signIn(page, ADMIN);
  await expect(page).toHaveURL(/\/admin$/);
  const rail = page.getByRole("navigation", { name: "Admin modules" });
  await expect(rail).toBeVisible();
  await expect(page.getByRole("heading", { name: "Today at a glance" })).toBeVisible();

  const modules: [string, string, string][] = [
    ["Debates", "/admin/debates", "Requests and agent checks"],
    ["Pricing", "/admin/pricing", "Pricing policy and model"],
    ["Negotiations", "/admin/negotiations", "Live negotiations"],
    ["Inventory", "/admin/inventory", "Venues and spaces"],
    ["Occupancy", "/admin/occupancy", "Occupancy data"],
    ["Telemetry", "/admin/telemetry", "Speed and conversion"],
    ["Overview", "/admin", "Today at a glance"],
  ];
  for (const [label, path, heading] of modules) {
    await rail.getByRole("link", { name: new RegExp(`^${label}`) }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }

  await page.goto("/admin/does-not-exist");
  await expect(page).toHaveURL(/\/admin$/);
});
