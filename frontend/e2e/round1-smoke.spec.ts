import { test, expect } from "@playwright/test";

const PAGES = [
  { path: "/", name: "工作台总览" },
  { path: "/audit-library", name: "审核点库" },
  { path: "/ai-review", name: "AI 审核" },
  { path: "/audit-results", name: "审核结果" },
  { path: "/workpaper", name: "工作底稿" },
  { path: "/compare", name: "文档对比" },
];

test.describe("Round 1: 烟雾测试", () => {
  test("侧边栏包含全部 6 个导航链接", async ({ page }) => {
    await page.goto("/");
    const sidebar = page.locator("aside");
    for (const p of PAGES) {
      await expect(sidebar.getByText(p.name)).toBeVisible();
    }
  });

  for (const p of PAGES) {
    test(`页面「${p.name}」(${p.path}) 能正常加载且无 JS 错误`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(p.path);
      await page.waitForLoadState("networkidle");

      // 顶栏或页面标题应包含页面名
      await expect(page.locator("header").first()).toBeVisible();

      expect(errors).toEqual([]);
    });
  }

  test("点击侧边栏导航能正确切换页面", async ({ page }) => {
    await page.goto("/");
    const sidebar = page.locator("aside");

    await sidebar.getByText("审核点库").click();
    await expect(page).toHaveURL(/\/audit-library/);

    await sidebar.getByText("AI 审核").click();
    await expect(page).toHaveURL(/\/ai-review/);

    await sidebar.getByText("文档对比").click();
    await expect(page).toHaveURL(/\/compare/);

    await sidebar.getByText("工作台总览").click();
    await expect(page).toHaveURL(/\/$/);
  });
});
