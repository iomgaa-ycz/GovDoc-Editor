import { test, expect } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "../../");

// LLM 调用耗时长（大文件提取可能 30+ 分钟），放宽超时
test.setTimeout(3_600_000); // 60 分钟

test.describe("Round 3: AI 提取审核点（LLM）", () => {
  test("上传法规文件触发 AI 提取并等待完成", async ({ page }) => {
    await page.goto("/audit-library");
    await page.waitForLoadState("networkidle");

    // 点击「上传」下拉 → 选择「AI 提取」菜单项
    await page.getByRole("button", { name: /上传/ }).click();
    await page.getByRole("menuitem", { name: "AI 提取" }).click();

    // 应进入 AI 提取子页面
    await expect(page.getByText("AI 智能提取审查要点")).toBeVisible();

    // 填写标题
    await page.getByPlaceholder(/政府采购法/).fill("四类违法违规指引");

    // 上传 DOC 文件
    const filePath = path.join(
      PROJECT_ROOT,
      `real_data/2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc`,
    );
    const fileInput = page.locator("input[type='file']");
    await fileInput.setInputFiles(filePath);

    // 点击「开始抽取」
    const extractBtn = page.getByRole("button", { name: /开始抽取/ });
    await expect(extractBtn).toBeEnabled();
    await extractBtn.click();

    // 等待提取完成（大文件 LLM 调用可能需要 30+ 分钟）
    await expect(page.getByText(/提取完成|已入库/)).toBeVisible({ timeout: 3_600_000 });

    // 返回列表验证有审核点
    await page.getByRole("button", { name: /返回列表/ }).click();
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Round 3: 启动 AI 审核（LLM）", () => {
  test("创建项目 → 上传招标文件 → 选择审核点 → 启动审核 → 等待完成", async ({ page }) => {
    // Step 1: 进入 AI 审核页面
    await page.goto("/ai-review");
    await page.waitForLoadState("networkidle");

    // Step 2: 创建新项目
    await page.getByPlaceholder("输入项目名称").fill("E2E测试-从化医院");
    await page.getByRole("button", { name: /创建/ }).click();
    await page.waitForTimeout(2000);

    // Step 3: 上传招标文件
    const tenderPath = path.join(
      PROJECT_ROOT,
      "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf",
    );
    const fileInput = page.locator("input[type='file']").first();
    await fileInput.setInputFiles(tenderPath);

    // 等待文件名显示在上传区域，然后点击上传按钮
    await page.waitForTimeout(500);
    // 上传按钮（非顶栏上传，是步骤内的小按钮）
    const uploadBtn = page.locator("button").filter({ hasText: "上传" }).last();
    await expect(uploadBtn).toBeVisible({ timeout: 5_000 });
    await uploadBtn.click();

    // 等待上传完成：出现绿色背景的已上传文件确认框（bg-status-ok-bg）
    await expect(page.locator(".bg-status-ok-bg")).toBeVisible({ timeout: 120_000 });

    // Step 4: 选择审核点（全选，最多选 5 个以控制耗时）
    const checkboxes = page.locator("input[type='checkbox']");
    await expect(checkboxes.first()).toBeVisible({ timeout: 10_000 });
    const count = await checkboxes.count();
    expect(count).toBeGreaterThan(0);
    const selectCount = Math.min(count, 5);
    for (let i = 0; i < selectCount; i++) {
      await checkboxes.nth(i).check();
    }

    // Step 5: 点击「开始审核」
    const startBtn = page.getByRole("button", { name: /开始审核/ });
    await expect(startBtn).toBeEnabled();
    await startBtn.click();

    // Step 6: 验证进入 Running 模式
    await expect(page.getByText("审核进行中")).toBeVisible({ timeout: 30_000 });

    // Step 7: 等待至少一个审核点完成（最长 10 分钟）
    await expect(
      page.locator(".bg-status-ok").first(),
    ).toBeVisible({ timeout: 600_000 });
  });
});
