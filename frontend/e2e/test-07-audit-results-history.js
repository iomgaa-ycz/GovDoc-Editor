async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');

  // Step 1: 进入 Dashboard，等待表格行加载（API 异步数据）
  console.log('Step 1: 进入 Dashboard，等待 table 加载');
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  const firstRow = page.locator('table tbody tr').first();
  await firstRow.waitFor({ timeout: 15000 });

  // Step 2: 检查箭头按钮状态
  console.log('Step 2: 检查箭头按钮状态');
  const arrowButtons = page.locator('table tbody tr td:last-child button');
  const buttonCount = await arrowButtons.count();
  if (buttonCount === 0) throw new Error('Dashboard 表格中未找到行末尾箭头按钮');

  let firstEnabledIndex = -1;
  for (let i = 0; i < buttonCount; i++) {
    const btn = arrowButtons.nth(i);
    const disabled = await btn.isDisabled();
    const title = await btn.getAttribute('title');
    if (title === '查看审核结果' && disabled) {
      throw new Error('有 auditRun 的项目箭头按钮被禁用');
    }
    if (title === '暂无可查看的审核运行' && !disabled) {
      throw new Error('无 auditRun 的项目箭头按钮未禁用');
    }
    if (!disabled && firstEnabledIndex === -1) firstEnabledIndex = i;
  }
  if (firstEnabledIndex === -1) throw new Error('Dashboard 中没有可点击的审核结果箭头按钮');
  console.log('Step 2: 找到 ' + buttonCount + ' 个箭头按钮，首个可点击按钮索引 ' + firstEnabledIndex);

  // Step 3: 点击第一个非 disabled 的箭头 button，等待 URL 变为 /audit-results
  console.log('Step 3: 点击第一个可点击箭头，等待跳转到 /audit-results');
  await arrowButtons.nth(firstEnabledIndex).click();
  await page.waitForURL('**/audit-results', { timeout: 10000 });

  // Step 4: 等待 3s，验证 point_runs 自动加载
  console.log('Step 4: 等待 3s，验证 point_runs 自动加载');
  await page.waitForTimeout(3000);
  const leftPanel = page.locator('.w-80').first();
  await leftPanel.waitFor({ timeout: 10000 });
  const emptyResult = page.getByText('暂无审核结果');
  if (await emptyResult.isVisible().catch(() => false)) {
    throw new Error('进入 /audit-results 后仍显示“暂无审核结果”，point_runs 未自动加载');
  }
  const pointButtons = leftPanel.locator('button');
  const pointButtonCount = await pointButtons.count();
  if (pointButtonCount === 0) throw new Error('左侧审核要点列表为空，未加载 point_runs');
  console.log('Step 4: 左侧已加载 ' + pointButtonCount + ' 个审核点');

  // Step 4b: 点击审核点验证右侧 PointInsight 显示
  console.log('Step 4b: 点击审核点验证 PointInsight');
  await pointButtons.first().click();
  await page.waitForTimeout(1500);
  const hasVerdict = await page.getByText('审核结论').isVisible().catch(() => false);
  const hasStatus = await page.getByText('审核状态').isVisible().catch(() => false);
  if (!hasVerdict && !hasStatus) throw new Error('点击审核点后右侧未显示 PointInsight');
  console.log('Step 4b: PointInsight 显示正确（' + (hasVerdict ? '有结论' : '有状态') + '）');

  // Step 5: 若有 Select 切换 run，尝试切换（可选，失败不报错）
  console.log('Step 5: 若有 Select 切换 run，尝试切换（可选）');
  try {
    const selectTrigger = page.locator('header button').first();
    await selectTrigger.click({ timeout: 3000 });
    const options = page.locator('[role="option"]');
    const optionCount = await options.count();
    if (optionCount > 1) {
      await options.nth(1).click();
      await page.waitForTimeout(1000);
      if (await emptyResult.isVisible().catch(() => false)) {
        await selectTrigger.click({ timeout: 3000 });
        await options.first().click();
        await page.waitForTimeout(1000);
      }
    } else {
      await page.keyboard.press('Escape').catch(() => {});
    }
  } catch (err) {
    console.log('Step 5: Select 切换跳过: ' + err.message);
    await page.keyboard.press('Escape').catch(() => {});
  }

  // Step 6: 检查所有审核点 button 的文字内容
  console.log('Step 6: 检查审核点标题无截断 ID');
  const pointButtonsAfterSelect = leftPanel.locator('button');
  const titles = [];
  const uuidLike = /^[0-9a-f-]{8,}$/i;
  const currentPointButtonCount = await pointButtonsAfterSelect.count();
  if (currentPointButtonCount === 0) throw new Error('Select 切换后左侧审核要点列表为空');
  for (let i = 0; i < currentPointButtonCount; i++) {
    const titleSpan = pointButtonsAfterSelect.nth(i).locator('span.text-sm').first();
    const text = ((await titleSpan.textContent().catch(() => '')) || '').trim();
    titles.push(text);
    if (uuidLike.test(text)) throw new Error('审核点标题显示为截断 ID: ' + text);
  }
  console.log('Step 6: 已检查 ' + titles.length + ' 个审核点标题');

  // Step 7: 等待 5s，重新检查左侧面板仍有审核点数据
  console.log('Step 7: 等待 5s，验证后台轮询不覆盖当前显示数据');
  await page.waitForTimeout(5000);
  if (await emptyResult.isVisible().catch(() => false)) {
    throw new Error('后台轮询覆盖当前数据，页面显示“暂无审核结果”');
  }
  const finalPointButtonCount = await leftPanel.locator('button').count();
  if (finalPointButtonCount === 0) throw new Error('后台轮询后左侧审核要点列表为空');
  console.log('Step 7: 轮询后左侧仍有 ' + finalPointButtonCount + ' 个审核点');

  // Step 8: 截图保存
  console.log('Step 8: 截图保存到 e2e/screenshots/07-audit-results-history.png');
  await page.screenshot({ path: 'e2e/screenshots/07-audit-results-history.png' });

  console.log('== test-07-audit-results-history 全部通过 ==');
}
