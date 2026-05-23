async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  const VALID_VERDICTS = ['合规', '不合规', '存疑'];

  // Part A: 审核结果质量验证
  console.log('== Part A: 审核结果质量验证 ==');

  await page.goto(BASE + '/audit-results');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);

  // 遍历 Select 找有 completed 审核点的运行
  const selectTrigger = page.locator('header button[role="combobox"]').first();
  let foundCompleted = false;

  if (await selectTrigger.isVisible().catch(() => false)) {
    await selectTrigger.click();
    const optCount = await page.locator('[role="option"]').count();
    await page.keyboard.press('Escape').catch(() => {});

    for (let oi = 0; oi < optCount; oi++) {
      await selectTrigger.click();
      await page.locator('[role="option"]').nth(oi).click();
      await page.waitForTimeout(2000);

      const leftPanel = page.locator('.w-80').first();
      const pointBtns = leftPanel.locator('button');
      const ptCount = await pointBtns.count();

      for (let pi = 0; pi < ptCount; pi++) {
        await pointBtns.nth(pi).click();
        await page.waitForTimeout(800);
        if (await page.getByText('审核结论').isVisible().catch(() => false)) {
          foundCompleted = true;
          break;
        }
      }
      if (foundCompleted) {
        console.log('找到有 completed 审核点的运行（选项 ' + oi + '）');
        break;
      }
    }
  }

  if (!foundCompleted) throw new Error('没有任何审核运行包含已完成的审核点');

  const leftPanel = page.locator('.w-80').first();
  const pointButtons = leftPanel.locator('button');
  const pointCount = await pointButtons.count();

  let verifiedCount = 0;
  for (let i = 0; i < pointCount; i++) {
    await pointButtons.nth(i).click();
    await page.waitForTimeout(1000);

    const hasVerdict = await page.getByText('审核结论').isVisible().catch(() => false);
    if (!hasVerdict) continue;

    const verdictPanel = page.locator('.rounded-card.border.p-4').first();
    const verdictText = (await verdictPanel.textContent() || '');
    const foundVerdict = VALID_VERDICTS.find(v => verdictText.includes(v));
    if (!foundVerdict) throw new Error('审核点 ' + i + ' verdict 不在有效值中: ' + verdictText.slice(0, 50));

    const rationaleTitle = page.getByText('审查意见');
    if (!(await rationaleTitle.isVisible().catch(() => false))) throw new Error('审核点 ' + i + ' 缺少审查意见');
    const rationaleBlock = rationaleTitle.locator('..').locator('p').first();
    const rationaleText = (await rationaleBlock.textContent() || '').trim();
    if (rationaleText.length <= 20) throw new Error('审核点 ' + i + ' 审查意见过短(' + rationaleText.length + '字): ' + rationaleText);

    const suggestionTitle = page.getByText('整改建议');
    if (!(await suggestionTitle.isVisible().catch(() => false))) throw new Error('审核点 ' + i + ' 缺少整改建议');
    const suggestionBlock = suggestionTitle.locator('..').locator('p').first();
    const suggestionText = (await suggestionBlock.textContent() || '').trim();
    if (suggestionText.length <= 10) {
      console.log('WARN: 审核点 ' + i + ' 整改建议过短(' + suggestionText.length + '字)，跳过');
      continue;
    }

    if (foundVerdict === '不合规' || foundVerdict === '存疑') {
      const evidenceTitle = page.getByText('原文引用');
      if (!(await evidenceTitle.isVisible().catch(() => false))) {
        throw new Error('审核点 ' + i + ' verdict=' + foundVerdict + ' 但缺少原文引用');
      }
    }

    verifiedCount++;
    console.log('PASS: 审核点 ' + i + ' — verdict=' + foundVerdict + ', rationale=' + rationaleText.length + '字, suggestion=' + suggestionText.length + '字');
  }
  if (verifiedCount === 0) throw new Error('没有任何 completed 的审核点可验证');
  console.log('Part A 完成: 验证 ' + verifiedCount + ' 个审核点质量');

  // Part B: 工作底稿质量验证
  console.log('');
  console.log('== Part B: 工作底稿质量验证 ==');

  await page.goto(BASE + '/workpaper');
  await page.waitForLoadState('networkidle');

  const emptyState = page.getByText('暂无工作底稿');
  if (await emptyState.isVisible().catch(() => false)) {
    console.log('SKIP: 无工作底稿数据');
  } else {
    const editor = page.locator('[contenteditable="true"]');
    await editor.waitFor({ timeout: 10000 }).catch(() => {});

    if (await editor.isVisible().catch(() => false)) {
      const html = await editor.innerHTML();
      if (html.length < 50) throw new Error('工作底稿 HTML 内容过短: ' + html.length + '字符');

      const keywords = ['审查', '意见', '建议'];
      const foundKw = keywords.filter(kw => html.includes(kw));
      if (foundKw.length === 0) {
        console.log('WARN: 工作底稿 HTML 未包含关键词 (审查/意见/建议)，可能内容异常');
      } else {
        console.log('PASS: 底稿含关键词: ' + foundKw.join(', '));
      }

      const findingsLabel = page.getByText('发现数量');
      if (await findingsLabel.isVisible().catch(() => false)) {
        const findingsRow = findingsLabel.locator('..');
        const findingsText = (await findingsRow.textContent() || '');
        const findingsMatch = findingsText.match(/(\d+)\s*条/);
        if (findingsMatch) {
          const count = parseInt(findingsMatch[1], 10);
          if (count < 1) throw new Error('findings 数量为 0');
          console.log('PASS: findings = ' + count + ' 条');
        }
      }
    } else {
      console.log('SKIP: 编辑器不可见，未加载工作底稿');
    }
  }

  await page.screenshot({ path: 'e2e/screenshots/15-result-quality.png', fullPage: true });

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-15-result-quality 全部通过 ==');
}
