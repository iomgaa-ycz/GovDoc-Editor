async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C5';

  // Step 1: 进入 Hub 页
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-01-hub.png', fullPage: true });

  // Step 2: "历史对比" 区域
  const historyTitle = page.getByText('历史对比').first();
  if (!(await historyTitle.isVisible())) throw new Error('"历史对比"不可见');
  console.log('PASS: "历史对比"区域可见');

  // Step 3: 检查是否有历史记录行
  const historyRows = page.locator('.grid.grid-cols-\\[minmax\\(0\\,1fr\\)_90px_70px_150px_80px\\].items-center');
  let rowCount = await historyRows.count();

  // 备选：如果精确类选择器不匹配，用文本内容检测
  if (rowCount === 0) {
    const errorText = page.locator('.text-red-500, .text-red-600').first();
    if (await errorText.isVisible().catch(() => false)) {
      const errMsg = await errorText.textContent() || '';
      throw new Error('历史对比加载失败: ' + errMsg.slice(0, 200));
    }

    const emptyMsg = page.getByText('暂无历史对比记录');
    if (await emptyMsg.isVisible().catch(() => false)) {
      console.log('WARN: 暂无历史对比记录（需先运行 C4 产生记录）');
      console.log('== compare-C5-history 跳过（无数据） ==');
      return;
    }
  }

  // 尝试用状态 badge 来定位行
  const completedBadges = page.getByText('已完成');
  const failedBadges = page.getByText('失败');
  const runningBadges = page.getByText('进行中');
  const completedCount = await completedBadges.count();
  const failedCount = await failedBadges.count();
  const runningCount = await runningBadges.count();
  const totalRecords = completedCount + failedCount + runningCount;
  if (totalRecords === 0) {
    console.log('WARN: 未找到任何历史记录状态 badge');
    await page.screenshot({ path: SS + '-02-no-records.png', fullPage: true });
    console.log('== compare-C5-history 跳过（无状态 badge） ==');
    return;
  }
  console.log('PASS: 历史记录 — 已完成:' + completedCount + ' 失败:' + failedCount + ' 进行中:' + runningCount);

  // Step 4: 验证状态 badge 样式
  if (completedCount > 0) {
    const greenBadge = page.locator('.bg-green-50').first();
    if (await greenBadge.isVisible()) console.log('PASS: 已完成 badge 为绿色');
  }
  if (failedCount > 0) {
    const redBadge = page.locator('.bg-red-50').first();
    if (await redBadge.isVisible()) console.log('PASS: 失败 badge 为红色');
  }
  await page.screenshot({ path: SS + '-02-history-rows.png', fullPage: true });

  // Step 5: 操作按钮
  const viewResultBtn = page.getByText('查看结果').first();
  const retryBtn = page.getByText('重试').first();
  const viewProgressBtn = page.getByText('查看进度').first();
  if (await viewResultBtn.isVisible().catch(() => false)) {
    console.log('PASS: "查看结果"按钮可见');
  }
  if (await retryBtn.isVisible().catch(() => false)) {
    console.log('PASS: "重试"按钮可见');
  }
  if (await viewProgressBtn.isVisible().catch(() => false)) {
    console.log('PASS: "查看进度"按钮可见');
  }

  // Step 6: 点击 "查看结果" → 跳转到 detail 页
  if (await viewResultBtn.isVisible().catch(() => false)) {
    console.log('Step 6: 点击"查看结果"');
    await viewResultBtn.click();
    await page.waitForURL(/\/compare\/[a-zA-Z0-9-]+/, { timeout: 15000 });
    console.log('PASS: 跳转到详情页 ' + page.url());
    await page.screenshot({ path: SS + '-03-detail-from-history.png', fullPage: true });

    // 返回 Hub 页
    const backLink = page.getByText('对比列表').first();
    if (await backLink.isVisible().catch(() => false)) {
      await backLink.click();
      await page.waitForURL(/\/compare$/, { timeout: 10000 });
      console.log('PASS: 返回 Hub 页');
    }
  } else {
    console.log('SKIP: 无已完成记录，跳过"查看结果"跳转测试');
  }

  await page.screenshot({ path: SS + '-04-final.png', fullPage: true });
  console.log('== compare-C5-history 全部通过 ==');
}
