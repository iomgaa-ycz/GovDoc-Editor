async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/cross-X1';
  const PDF_PATH = 'e2e/.test-data/E2E测试招标文件.pdf';

  // ── 跨页面测试：上传文件后立即在 AI 审查文件选择器中可见 ──

  // Step 1: 先检查 AI 审查选择器中的当前文件列表
  console.log('Step 1: 记录 AI 审查文件选择器初始状态');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '新建审查' }).click();
  const drawer = page.locator('.fixed.inset-0.z-50').filter({ hasText: '新建审查任务' });
  await drawer.waitFor({ state: 'visible', timeout: 10000 });

  await drawer.getByRole('button', { name: '选择招标文书' }).click();
  const picker = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' }).last();
  await picker.waitFor({ state: 'visible', timeout: 10000 });

  const initialFileCount = await picker.locator('.overflow-y-auto button.w-full, .overflow-y-auto [role="button"]').count();
  console.log('INFO: 初始文件选择器有 ' + initialFileCount + ' 个文件');

  // 关闭选择器和抽屉
  await picker.getByRole('button', { name: '取消' }).first().click().catch(() => {});
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1000);

  // Step 2: 切到文件管理，上传新文件
  console.log('Step 2: 切到文件管理上传新文件');
  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');

  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(PDF_PATH);

  // 等文件出现
  const fileRow = page.getByText('E2E测试招标文件').first();
  await fileRow.waitFor({ timeout: 120000 });
  console.log('PASS: 文件上传成功');

  // 等待转换完成或至少转换中
  await page.waitForTimeout(3000);
  await page.screenshot({ path: SS + '-01-uploaded.png', fullPage: true });

  // Step 3: 切回 AI 审查，打开文件选择器
  console.log('Step 3: 切回 AI 审查，验证新文件可见');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '新建审查' }).click();
  const drawer2 = page.locator('.fixed.inset-0.z-50').filter({ hasText: '新建审查任务' });
  await drawer2.waitFor({ state: 'visible', timeout: 10000 });

  await drawer2.getByRole('button', { name: '选择招标文书' }).click();
  const picker2 = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' }).last();
  await picker2.waitFor({ state: 'visible', timeout: 10000 });

  // 搜索刚上传的文件
  const searchInput = picker2.locator('input[placeholder="搜索文件名..."]').first();
  if (await searchInput.isVisible().catch(() => false)) {
    await searchInput.fill('E2E测试招标文件');
    await page.waitForTimeout(1000);
  }

  // 验证能找到
  const newFileItem = picker2.getByText('E2E测试招标文件').first();
  if (await newFileItem.isVisible().catch(() => false)) {
    console.log('PASS: 新上传的文件在选择器中可见');
  } else {
    throw new Error('新上传的文件在选择器中不可见');
  }

  await page.screenshot({ path: SS + '-02-found-in-picker.png', fullPage: true });
  console.log('== cross-X1-file-to-review 全部通过 ==');
}
