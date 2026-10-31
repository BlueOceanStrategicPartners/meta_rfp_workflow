import { test, expect } from "@playwright/test";

test("client workspace loads orb and composer toggle", async ({ page }) => {
  const start = Date.now();
  await page.goto("/client");
  await expect(page.getByLabel("Toggle composer")).toBeVisible();
  await page.getByLabel("Toggle composer").click();
  await expect(page.getByPlaceholder("Type your RFP details...")).toBeVisible();
  const elapsed = Date.now() - start;
  expect(elapsed).toBeLessThan(120_000);
});

test("composer send triggers voice status", async ({ page }) => {
  await page.goto("/client");
  await page.getByLabel("Toggle composer").click();
  await page.getByPlaceholder("Type your RFP details...").fill("hi");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByText(/Live voice · SeamlessM4T|Enable voice|Voice playback failed/i),
  ).toBeVisible({ timeout: 20_000 });
});
