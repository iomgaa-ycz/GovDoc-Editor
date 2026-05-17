import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "../../");

test.describe("Round 2: 导入审核点（无 LLM）", () => {
  test("通过表格导入审核点并在列表中显示", async ({ page }) => {
    // 导航到审核点库
    await page.goto("/audit-library");
    await page.waitForLoadState("networkidle");

    // 点击「上传」下拉菜单
    await page.getByRole("button", { name: /上传/ }).click();
    // 选择「导入审查点表格」
    await page.getByText("导入审查点表格").click();

    // 应进入导入子页面
    await expect(page.getByText("导入审查点表格").first()).toBeVisible();

    // 上传 XLS 文件
    const filePath = path.join(PROJECT_ROOT, "real_data/附件9 处理处罚标准.xls");
    const fileInput = page.locator("input[type='file']");
    await fileInput.setInputFiles(filePath);

    // 点击「启动解析并导入库」
    const importBtn = page.getByRole("button", { name: /启动解析|导入/ });
    await expect(importBtn).toBeEnabled();
    await importBtn.click();

    // 等待成功提示
    await expect(page.getByText(/成功导入/)).toBeVisible({ timeout: 30_000 });

    // 返回列表
    await page.getByRole("button", { name: /返回列表/ }).click();

    // 列表中应有审核点
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Round 2: 文件对比（无 LLM）", () => {
  test("上传两份 DOCX 并显示对比结果", async ({ page }) => {
    await page.goto("/compare");
    await page.waitForLoadState("networkidle");

    // 上传文档 A
    const fileInputs = page.locator("input[type='file']");
    const docA = path.join(
      PROJECT_ROOT,
      "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx",
    );
    const docB = path.join(
      PROJECT_ROOT,
      "real_data/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目.docx",
    );
    await fileInputs.nth(0).setInputFiles(docA);
    await fileInputs.nth(1).setInputFiles(docB);

    // 点击「开始对比」
    const compareBtn = page.getByRole("button", { name: /开始对比/ });
    await expect(compareBtn).toBeEnabled();
    await compareBtn.click();

    // 等待结果显示（匹配总数指标卡出现）
    await expect(page.getByText("匹配总数")).toBeVisible({ timeout: 60_000 });

    // 验证有指标卡片（MetricCard 的 label 在 .text-sm 中）
    await expect(page.locator(".border-l-4").filter({ hasText: "相同段落" })).toBeVisible();
    await expect(page.locator(".border-l-4").filter({ hasText: "相同句子" })).toBeVisible();

    // 验证有匹配清单
    await expect(page.locator("h3").filter({ hasText: "匹配清单" })).toBeVisible();
  });
});
