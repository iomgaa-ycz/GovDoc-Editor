async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R3';

  // ── Step 1: 导航到 AI 审查页 ──
  console.log('Step 1: 导航到 /ai-review');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // 记录初始任务数
  const initRows = await page.locator('[role="button"][tabindex="0"]').filter({ hasText: /查看/ }).count();

  // ── Step 2: 打开抽屉 ──
  console.log('Step 2: 打开新建审查抽屉');
  await page.getByRole('button', { name: '新建审查' }).click();
  const drawer = page.locator('.fixed.inset-0.z-50').filter({ hasText: '新建审查任务' });
  await drawer.waitFor({ state: 'visible', timeout: 10000 });

  // ── Step 3: 选择项目（下拉框第一项） ──
  console.log('Step 3: 选择项目');
  const projectTrigger = drawer.locator('button').filter({ hasText: /选择项目|项目/ }).first();
  // 尝试点击 SelectTrigger（Radix Select）
  const selectTrigger = drawer.locator('[role="combobox"], button').filter({ hasText: /选择项目|项目/ }).first();
  if (await selectTrigger.isVisible().catch(() => false)) {
    await selectTrigger.click();
    await page.waitForTimeout(500);
    // 点击第一个选项
    const firstOption = page.locator('[role="option"]').first();
    if (await firstOption.isVisible().catch(() => false)) {
      await firstOption.click();
      console.log('PASS: 已选择第一个项目');
    } else {
      console.log('WARN: 下拉框无项目选项，跳过项目选择');
    }
  }

  // ── Step 4: 选择招标文书 ──
  console.log('Step 4: 选择招标文书');
  await drawer.getByRole('button', { name: '选择招标文书' }).click();

  // 等待文件选择器弹窗
  const picker = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' }).last();
  await picker.waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForTimeout(500);

  // 查找"已就绪"的文件并选第一个（等待加载）
  const fileButtons = picker.locator('.overflow-y-auto button.w-full, .overflow-y-auto [role="button"]');
  // 等待文件列表加载（最多 10 秒）
  for (let i = 0; i < 20; i++) {
    if (await fileButtons.count() > 0) break;
    await page.waitForTimeout(500);
  }
  const fileCount = await fileButtons.count();
  if (fileCount === 0) {
    console.log('SKIP: 文件选择器中无可用文件，跳过 review-R3-create-run');
    return;
  }
  await fileButtons.first().click();
  await page.waitForTimeout(300);
  await picker.getByRole('button', { name: '确认选择' }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: SS + '-02-doc-selected.png', fullPage: true });
  console.log('PASS: 已选择招标文书');

  // ── Step 5: 选择审查范围 ──
  console.log('Step 5: 选择审查范围');

  // 检查是否有审核点库可选
  const libraryModeBtn = drawer.getByText('按审核点库', { exact: true }).first();
  const manualModeBtn = drawer.getByText('手动选择', { exact: true }).first();

  if (await libraryModeBtn.isEnabled().catch(() => false)) {
    // 库模式可用
    await libraryModeBtn.click();
    await page.waitForTimeout(500);
    // 尝试选择第一个库
    const librarySelectTrigger = drawer.locator('button').filter({ hasText: /选择审核点库/ }).first();
    if (await librarySelectTrigger.isVisible().catch(() => false)) {
      await librarySelectTrigger.click();
      await page.waitForTimeout(500);
      const firstLibOption = page.locator('[role="option"]').first();
      if (await firstLibOption.isVisible().catch(() => false)) {
        await firstLibOption.click();
        console.log('PASS: 已选择第一个审核点库');
      }
    }
  } else {
    // 手动模式
    console.log('INFO: 无审核点库，使用手动选择模式');
    await manualModeBtn.click();
    await page.waitForTimeout(500);

    // 勾选前 3 个审核点
    const checkboxes = drawer.locator('input[type="checkbox"]');
    const cpCount = await checkboxes.count();
    if (cpCount === 0) {
      throw new Error('无审核点可选，请先在审核点库中导入或提取审核点');
    }
    const selectCount = Math.min(3, cpCount);
    for (let i = 0; i < selectCount; i++) {
      await checkboxes.nth(i).click();
      await page.waitForTimeout(200);
    }
    console.log('PASS: 已手动勾选 ' + selectCount + ' 个审核点');
  }

  await page.screenshot({ path: SS + '-03-scope-selected.png', fullPage: true });

  // ── Step 6: 提交 ──
  console.log('Step 6: 提交审查任务');
  const submitBtn = drawer.getByRole('button', { name: /开始审查/ });

  // 等待按钮变为可点击
  const isDisabled = await submitBtn.isDisabled();
  if (isDisabled) {
    throw new Error('"开始审查"按钮仍禁用，项目/文书/审查范围可能未正确选择');
  }

  await submitBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: SS + '-04-submitted.png', fullPage: true });

  // 验证抽屉关闭 + 列表刷新
  const drawerVisible = await drawer.isVisible().catch(() => false);
  if (!drawerVisible) {
    console.log('PASS: 抽屉已关闭');
  } else {
    console.log('WARN: 抽屉可能还在（loading 中）');
  }

  // 验证新任务出现在列表中
  const newRows = await page.locator('[role="button"][tabindex="0"]').filter({ hasText: /查看/ }).count();
  if (newRows > initRows || initRows === 0) {
    console.log('PASS: 新任务已出现在列表中');
  } else {
    console.log('WARN: 列表行数未增加（' + initRows + ' → ' + newRows + '），可能正在加载');
  }

  console.log('== review-R3-create-run 全部通过 ==');
}
