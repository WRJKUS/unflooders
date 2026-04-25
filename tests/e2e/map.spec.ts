import { test, expect } from "@playwright/test"

test("loads Limburg FloodFarm map shell", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByText("Limburg FloodFarm Risk Mapper (MaasGuard)")).toBeVisible()
  await expect(page.getByText("Layers")).toBeVisible()
})
