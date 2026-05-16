import { expect, test } from "@playwright/test";

test("first screen is the ASIP evidence workbench", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("asip-workbench")).toBeVisible();
  await expect(page.getByRole("banner")).toContainText("ASIP Evidence Workbench");
  await expect(page.getByRole("navigation", { name: "ASIP sections" })).toContainText("Evidence Search");
  await expect(page.getByRole("textbox", { name: "Evidence query" })).toHaveValue(
    "Who writes regGCVM_L2_CNTL?"
  );
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("GCVM_L2_CNTL");
  await expect(page.getByTestId("relationship-panel")).toContainText("has_field");
});
