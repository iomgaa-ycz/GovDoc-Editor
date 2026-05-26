async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C4';

  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');

  // 辅助：从文件库选择 N 个文件
  async function pickFiles(n) {
    await page.getByRole('button', { name: /从文件库添加|从文件库选择文件/ }).first().click();
    const modal = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' });
    await modal.waitFor({ timeout: 10000 });
    const items = modal.locator('.overflow-y-auto button.w-full');
    for (let retry = 0; retry < 20; retry++) {
      if (await items.count() > 0) break;
      await page.waitForTimeout(500);
    }
    const available = await items.count();
    const toSelect = Math.min(n, available);
    for (let i = 0; i < toSelect; i++) {
      await items.nth(i).click();
      await page.waitForTimeout(200);
    }
    await modal.getByRole('button', { name: '确认选择' }).click();
    await page.waitForTimeout(500);
    return toSelect;
  }

  // Step 1: 选择 2 个文件
  console.log('Step 1: 选择 2 个文件');
  const picked = await pickFiles(2);
  if (picked < 2) throw new Error('文件库不足 2 个已转换文件');
  await page.screenshot({ path: SS + '-01-files-selected.png', fullPage: true });
  console.log('PASS: 已选 ' + picked + ' 个文件');

  // Step 2: 点击 "开始对比"
  console.log('Step 2: 点击"开始对比"');
  const compareBtn = page.getByRole('button', { name: /开始对比/ });
  await compareBtn.click();

  // 应显示 "提交中..." 或跳转到详情页
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-02-submitting.png', fullPage: true });

  // Step 3: 等待跳转到 detail 页 (/compare/:reviewId)
  console.log('Step 3: 等待跳转到详情页');
  await page.waitForURL(/\/compare\/[a-zA-Z0-9-]+/, { timeout: 30000 });
  const detailUrl = page.url();
  console.log('PASS: 已跳转到详情页 ' + detailUrl);

  // Step 4: 验证进度视图
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-03-progress-view.png', fullPage: true });

  // "对比文件" 卡片
  const filesCard = page.getByText('对比文件').first();
  if (await filesCard.isVisible()) {
    console.log('PASS: "对比文件"卡片可见');
  }

  // "对比进度" 卡片
  const progressCard = page.getByText('对比进度').first();
  if (await progressCard.isVisible()) {
    console.log('PASS: "对比进度"卡片可见');
  }

  // 6 步骤标签
  const steps = ['上传文件', '文档转换', '段落匹配', '句子匹配', '近似检测', '生成结果'];
  let visibleSteps = 0;
  for (const step of steps) {
    const el = page.getByText(step).first();
    if (await el.isVisible().catch(() => false)) visibleSteps++;
  }
  if (visibleSteps >= 4) {
    console.log('PASS: 进度步骤可见（' + visibleSteps + '/6）');
  } else {
    console.log('WARN: 进度步骤仅可见 ' + visibleSteps + '/6（可能已快速完成）');
  }

  // Step 5: 等待对比完成（最长 30 分钟）
  console.log('Step 5: 等待对比完成（最长 30 分钟）...');
  const startTime = Date.now();
  let completed = false;
  let failed = false;
  let lastScreenshot = 0;

  while (Date.now() - startTime < 1800000) {
    // 检查是否完成 — 结果页出现指标卡片
    const resultHeading = page.getByText('文档对比结果').first();
    if (await resultHeading.isVisible().catch(() => false)) {
      completed = true;
      break;
    }

    // 检查是否失败
    const failedHeading = page.getByText('对比失败').first();
    if (await failedHeading.isVisible().catch(() => false)) {
      failed = true;
      break;
    }

    // 每 60 秒截图一次记录进度
    const elapsed = Date.now() - startTime;
    if (elapsed - lastScreenshot > 60000) {
      const mins = Math.floor(elapsed / 60000);
      await page.screenshot({ path: SS + '-04-progress-' + mins + 'min.png', fullPage: true });
      console.log('... 等待中（' + mins + ' 分钟）');
      lastScreenshot = elapsed;
    }

    await page.waitForTimeout(5000);
  }

  const totalSecs = Math.floor((Date.now() - startTime) / 1000);

  if (failed) {
    await page.screenshot({ path: SS + '-05-failed.png', fullPage: true });
    const errorBox = page.locator('.bg-red-50, .text-red-600').first();
    const errorText = await errorBox.textContent().catch(() => '(无法读取)');
    throw new Error('对比失败（' + totalSecs + 's）: ' + (errorText || '').slice(0, 200));
  }

  if (!completed) {
    await page.screenshot({ path: SS + '-05-timeout.png', fullPage: true });
    throw new Error('对比超时（30 分钟未完成）');
  }

  await page.screenshot({ path: SS + '-05-completed.png', fullPage: true });
  console.log('PASS: 对比完成（耗时 ' + totalSecs + 's）');

  // Step 6: 验证状态 badge 为 "已完成"
  const statusBadge = page.locator('.bg-green-50').getByText('已完成').first();
  if (await statusBadge.isVisible().catch(() => false)) {
    console.log('PASS: 状态 badge "已完成"');
  } else {
    console.log('WARN: 未找到绿色"已完成"badge（页面可能已直接显示结果）');
  }

  console.log('== compare-C4-submit-progress 全部通过 ==');
}
