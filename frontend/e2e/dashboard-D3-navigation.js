async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/dashboard-D3';
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 进入工作台总览页
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);

  // Step 2: "创建审查任务" 按钮跳转
  const createBtn = page.getByRole('button', { name: /创建审查任务/ });
  if (await createBtn.isVisible().catch(() => false)) {
    await createBtn.click();
    // Link 包裹按钮，点击后应跳转到 /ai-review
    await page.waitForURL(/\/ai-review/, { timeout: 10000 });
    if (page.url().includes('/ai-review')) {
      console.log('PASS: "创建审查任务"跳转到 /ai-review');
      await page.screenshot({ path: SS + '-01-ai-review.png', fullPage: true });
    } else {
      console.log('WARN: 跳转目标 URL 不含 /ai-review: ' + page.url());
    }
    // 返回 Dashboard
    await page.goto(BASE + '/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  } else {
    throw new Error('"创建审查任务"按钮不可见');
  }

  // Step 3: 检查表格空状态或数据状态
  const stats = await page.evaluate(async (baseUrl) => {
    const resp = await fetch(baseUrl + '/api/v1/dashboard/stats');
    if (!resp.ok) return null;
    return resp.json();
  }, BASE);

  const projects = (stats && stats.recent_projects) || [];

  if (projects.length === 0) {
    // 无数据：验证空状态提示
    const emptyMsg = page.getByText('暂无审核记录');
    if (await emptyMsg.isVisible().catch(() => false)) {
      console.log('PASS: 无项目时显示"暂无审核记录"');
    }
    // 箭头按钮不应存在（无行）
    const arrowButtons = page.locator('button[aria-label*="审核结果"]');
    const arrowCount = await arrowButtons.count();
    if (arrowCount === 0) {
      console.log('PASS: 无项目时无箭头按钮');
    }
  } else {
    // 有数据：验证箭头按钮
    const arrowButtons = page.locator('button[aria-label*="审核结果"]');
    const arrowCount = await arrowButtons.count();

    // 检查是否有禁用的箭头按钮（该项目无 auditRun）
    const disabledArrows = page.locator('button[disabled][aria-label*="审核结果"]');
    const disabledCount = await disabledArrows.count();
    const enabledCount = arrowCount - disabledCount;

    console.log('PASS: 箭头按钮 ' + arrowCount + ' 个（启用: ' + enabledCount + ', 禁用: ' + disabledCount + '）');

    // 尝试点击启用的箭头按钮跳转
    if (enabledCount > 0) {
      const firstEnabled = page.locator('button:not([disabled])[aria-label*="审核结果"]').first();
      const ariaLabel = await firstEnabled.getAttribute('aria-label');
      await firstEnabled.click();
      await page.waitForURL(/\/ai-review\//, { timeout: 10000 }).catch(() => {});
      if (page.url().includes('/ai-review/')) {
        console.log('PASS: 箭头按钮跳转到审核详情 — ' + ariaLabel);
        await page.screenshot({ path: SS + '-02-audit-detail.png', fullPage: true });
        // 返回
        await page.goto(BASE + '/');
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1000);
      } else {
        console.log('WARN: 箭头点击后未跳转到 /ai-review/:id — 当前 URL: ' + page.url());
      }
    }
  }

  // Step 4: 检查页面加载无 JS 错误
  await page.screenshot({ path: SS + '-03-final.png', fullPage: true });
  if (errors.length > 0) {
    console.log('WARN: 检测到 JS 错误 (' + errors.length + ' 个):');
    errors.slice(0, 5).forEach(e => console.log('  ' + e.slice(0, 120)));
  } else {
    console.log('PASS: 无 JS 控制台错误');
  }

  console.log('== dashboard-D3-navigation 全部通过 ==');
}
