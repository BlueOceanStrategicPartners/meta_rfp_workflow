import { expect, test, type Page } from "@playwright/test";

// Needs both servers running and the demo accounts seeded (seed_admin_demo).
const ADMIN = { email: "admin@demo.local", password: "admin12345" };
const DESIGNER = { email: "designer@demo.local", password: "demo12345" };

async function signIn(page: Page, who: { email: string; password: string }) {
  await page.goto("/admin");
  await expect(page.getByText("Sign in with your admin account")).toBeVisible();
  await page.locator('input[type="email"]').fill(who.email);
  await page.locator('input[type="password"]').fill(who.password);
  await page.getByRole("button", { name: /sign in with email/i }).click();
}

test("shows the admin sign-in form at /admin", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin Command Center" })).toBeVisible();
  await expect(page.getByText("Sign in with your admin account")).toBeVisible();
});

test("rejects a designer account with a role message", async ({ page }) => {
  await signIn(page, DESIGNER);
  await expect(page.getByText("Signed in as DESIGNER. Sign in with an admin account.")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Admin modules" })).toHaveCount(0);
});

test("demo admin signs in and can visit every module from the rail", async ({ page }) => {
  await signIn(page, ADMIN);
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
    // The Admin tab in the app header stays active on every sub-route.
    await expect(page.locator(".app-nav-link-active")).toHaveText("Admin");
  }

  // Unknown admin paths go back to the overview.
  await page.goto("/admin/does-not-exist");
  await expect(page).toHaveURL(/\/admin$/);
});
