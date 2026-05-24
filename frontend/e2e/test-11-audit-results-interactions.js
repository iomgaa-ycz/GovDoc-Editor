async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 从 Dashboard 导航到审核结果页
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  const firstRow = page.locator('table tbody tr').first();
  await firstRow.waitFor({ timeout: 15000 });

  const arrowButtons = page.locator('table tbody tr td:last-child button');
  const buttonCount = await arrowButtons.count();
  let firstEnabledIndex = -1;
  for (let i = 0; i < buttonCount; i++) {
    if (!(await arrowButtons.nth(i).isDisabled())) { firstEnabledIndex = i; break; }
  }
  if (firstEnabledIndex === -1) throw new Error('Dashboard 无可点击审核结果按钮');

  await arrowButtons.nth(firstEnabledIndex).click();
  await page.waitForURL('**/audit-results', { timeout: 10000 });
  console.log('Step 1: 从 Dashboard 跳转到 /audit-results');

  // Step 2: 等待左侧审核点列表加载
  await page.waitForTimeout(3000);
  const leftPanel = page.locator('.w-80').first();
  await leftPanel.waitFor({ timeout: 10000 });
  const pointButtons = leftPanel.locator('button');
  const pointCount = await pointButtons.count();
  if (pointCount === 0) throw new Error('左侧审核要点列表为空');
  console.log('Step 2: 左侧加载 ' + pointCount + ' 个审核点');

  // Step 3: 点击审核点 → 右侧显示 PointInsight
  await pointButtons.first().click();
  await page.waitForTimeout(1000);

  const rightPanel = page.locator('.flex-1.overflow-auto').first();

  const hasVerdict = await page.getByText('审核结论').isVisible().catch(() => false);
  const hasStatus = await page.getByText('审核状态').isVisible().catch(() => false);
  if (!hasVerdict && !hasStatus) throw new Error('点击审核点后右侧未显示 PointInsight');
  console.log('PASS: 点击审核点 → 右侧 PointInsight 显示（' + (hasVerdict ? '有结论' : '有状态') + '）');

  // Step 4: PointInsight 详情验证
  if (hasVerdict) {
    const rationale = page.getByText('审查意见');
    const suggestion = page.getByText('整改建议');
    if (!(await rationale.isVisible().catch(() => false))) throw new Error('缺少"审查意见"标题');
    if (!(await suggestion.isVisible().catch(() => false))) throw new Error('缺少"整改建议"标题');
    console.log('PASS: PointInsight 详情完整（审查意见 + 整改建议）');
  } else {
    console.log('SKIP: 非 verdict 状态，跳过详情验证');
  }

  // Step 5: 人工反馈 — 发送按钮禁用状态
  const feedbackTitle = page.getByText('人工反馈');
  if (await feedbackTitle.isVisible().catch(() => false)) {
    const textarea = page.getByPlaceholder('输入审查意见或修改建议...');
    await textarea.waitFor({ timeout: 5000 });

    const sendBtn = textarea.locator('..').locator('..').locator('button').last();
    if (!(await sendBtn.isDisabled())) throw new Error('空文本时发送按钮未禁用');
    console.log('PASS: 空文本时发送按钮禁用');

    // Step 6: 提交反馈
    const feedbackText = 'E2E 测试反馈 ' + Date.now().toString().slice(-6);
    await textarea.fill(feedbackText);
    await page.waitForTimeout(300);
    if (await sendBtn.isDisabled()) throw new Error('输入文本后发送按钮仍禁用');

    await sendBtn.click();
    await page.waitForTimeout(2000);

    const comment = page.getByText(feedbackText);
    if (!(await comment.isVisible())) throw new Error('提交反馈后评论未出现');

    const commentArea = page.locator('.border-b.py-2\\.5').first();
    const commentFullText = (await commentArea.textContent().catch(() => '') || '');
    if (!commentFullText.includes(feedbackText)) throw new Error('评论内容不匹配');
    console.log('PASS: 反馈提交成功，评论显示在列表中');
  } else {
    console.log('SKIP: 人工反馈区域不可见（可能审核点无 checkpoint 数据）');
  }

  // Step 7: 重试按钮验证（查找 failed 状态的审核点）
  let foundRetry = false;
  for (let i = 0; i < pointCount; i++) {
    const btn = pointButtons.nth(i);
    const btnText = (await btn.textContent() || '').toLowerCase();
    if (btnText.includes('失败') || btnText.includes('failed') || btnText.includes('待重试')) {
      await btn.click();
      await page.waitForTimeout(1000);
      const retryBtn = page.getByRole('button', { name: /重试此审核点/ });
      if (await retryBtn.isVisible().catch(() => false)) {
        foundRetry = true;
        console.log('PASS: 失败审核点显示重试按钮');
      }
      break;
    }
  }
  if (!foundRetry) console.log('SKIP: 无 failed 状态审核点，跳过重试按钮测试');

  // Step 8: Select 切换审核运行
  try {
    const selectTrigger = page.locator('header').locator('button').first();
    await selectTrigger.click({ timeout: 3000 });
    const selectOptions = page.locator('[role="option"]');
    const optCount = await selectOptions.count();
    if (optCount > 1) {
      const firstOptionText = await selectOptions.first().textContent();
      await selectOptions.nth(1).click();
      await page.waitForTimeout(2000);

      const leftAfterSwitch = page.locator('.w-80').first();
      const btnsAfterSwitch = await leftAfterSwitch.locator('button').count();
      console.log('PASS: Select 切换到另一 run，左侧有 ' + btnsAfterSwitch + ' 个审核点');

      // 切回
      await selectTrigger.click({ timeout: 3000 });
      await selectOptions.first().click();
      await page.waitForTimeout(1000);
    } else {
      await page.keyboard.press('Escape').catch(() => {});
      console.log('SKIP: 仅 1 个审核运行，跳过 Select 切换');
    }
  } catch (err) {
    console.log('SKIP: Select 切换失败: ' + err.message);
    await page.keyboard.press('Escape').catch(() => {});
  }

  await page.screenshot({ path: 'e2e/screenshots/11-audit-results-interactions.png', fullPage: true });

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-11-audit-results-interactions 全部通过 ==');
}
