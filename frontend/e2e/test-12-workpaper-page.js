async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 进入工作底稿页面
  await page.goto(BASE + '/workpaper');
  await page.waitForLoadState('networkidle');
  console.log('Step 1: 进入工作底稿页面');

  // Step 2: 判断空状态 vs 有数据
  const emptyState = page.getByText('暂无工作底稿');
  const isEmptyState = await emptyState.isVisible().catch(() => false);

  if (isEmptyState) {
    // 空状态路径验证
    const createLink = page.getByRole('link', { name: /创建审查任务/ });
    if (!(await createLink.isVisible())) throw new Error('空状态缺少"创建审查任务"链接');

    const historyLink = page.getByRole('link', { name: /查看历史记录/ });
    if (!(await historyLink.isVisible())) throw new Error('空状态缺少"查看历史记录"链接');

    // 验证链接跳转
    await createLink.click();
    await page.waitForURL('**/ai-review', { timeout: 5000 });
    console.log('PASS: 空状态 → "创建审查任务"跳转正确');

    await page.goto(BASE + '/workpaper');
    await page.waitForLoadState('networkidle');
    await historyLink.waitFor({ timeout: 5000 });
    await historyLink.click();
    await page.waitForURL('**/audit-results', { timeout: 5000 });
    console.log('PASS: 空状态 → "查看历史记录"跳转正确');

    await page.screenshot({ path: 'e2e/screenshots/12-workpaper-empty.png' });
    console.log('== test-12-workpaper-page 全部通过（空状态路径） ==');
    return;
  }

  // 有数据路径
  console.log('Step 2: 有审核运行数据，进入编辑路径');

  // Step 3: 遍历 Select 选项，找有底稿内容的运行
  const selectTrigger = page.locator('header button[role="combobox"]').first();
  let editorLoaded = false;
  if (await selectTrigger.isVisible().catch(() => false)) {
    await selectTrigger.click();
    const optCount = await page.locator('[role="option"]').count();
    await page.keyboard.press('Escape').catch(() => {});

    for (let i = 0; i < optCount; i++) {
      await selectTrigger.click();
      await page.locator('[role="option"]').nth(i).click();
      await page.waitForTimeout(2000);
      const editor = page.locator('[contenteditable="true"]');
      if (await editor.isVisible().catch(() => false)) {
        const text = (await editor.textContent() || '').trim();
        if (text.length > 10) {
          editorLoaded = true;
          console.log('PASS: 找到有内容的运行（选项 ' + i + '，' + text.length + ' 字）');
          break;
        }
      }
    }
    if (!editorLoaded) console.log('SKIP: 所有运行均无底稿内容');
  }

  if (editorLoaded) {
  // Step 4: Toolbar 按钮验证
  const toolbarButtons = [
    { title: '加粗', icon: 'bold' },
    { title: '标题', icon: 'heading' },
    { title: '引用', icon: 'quote' },
    { title: '有序列表', icon: 'list' },
  ];
  for (const btn of toolbarButtons) {
    const el = page.locator(`button[title="${btn.title}"]`);
    if (!(await el.isVisible().catch(() => false))) throw new Error('Toolbar 按钮缺失: ' + btn.title);
  }
  console.log('PASS: 4 个 Toolbar 按钮完整（加粗/标题/引用/有序列表）');

  // Step 5: 验证编辑器可交互
  const editor = page.locator('[contenteditable="true"]');
  if (await editor.isVisible().catch(() => false)) {
    const editorText = (await editor.textContent() || '').trim();
    if (editorText.length < 10) throw new Error('编辑器内容过短或为空: ' + editorText.length + '字');
    await editor.click();
    await page.waitForTimeout(300);
    const isFocused = await editor.evaluate(el => el === document.activeElement || el.contains(document.activeElement));
    if (!isFocused) throw new Error('编辑器点击后未获得焦点');
    console.log('PASS: 编辑器有内容(' + editorText.length + '字)且可聚焦');
  } else {
    console.log('SKIP: 编辑器不可见（可能未加载 workpaper）');
  }
  }

  // Step 6: 文档信息卡片
  const docInfoCard = page.getByText('文档信息');
  if (!(await docInfoCard.isVisible().catch(() => false))) throw new Error('文档信息卡片不可见');

  const saveStatusLabel = page.getByText('保存状态');
  if (!(await saveStatusLabel.isVisible().catch(() => false))) throw new Error('保存状态标签不可见');

  const finalizeStatusLabel = page.getByText('定稿状态');
  if (!(await finalizeStatusLabel.isVisible().catch(() => false))) throw new Error('定稿状态标签不可见');
  console.log('PASS: 文档信息卡片完整');

  // Step 7: 保存按钮
  const saveBtn = page.getByRole('button', { name: /保存/ }).first();
  if (!(await saveBtn.isVisible().catch(() => false))) throw new Error('保存按钮不可见');
  console.log('PASS: 保存按钮可见');

  // Step 8: 定稿按钮
  const finalizeBtn = page.getByRole('button', { name: /定稿/ }).first();
  if (!(await finalizeBtn.isVisible().catch(() => false))) throw new Error('定稿按钮不可见');
  console.log('PASS: 定稿按钮可见');

  // Step 9: 导出 Word 按钮
  const exportBtn = page.getByRole('button', { name: /导出 Word/ });
  if (!(await exportBtn.isVisible().catch(() => false))) throw new Error('导出 Word 按钮不可见');

  const finalizeStatusText = (await page.locator('.space-y-2').first().textContent() || '');
  if (!finalizeStatusText.includes('已定稿')) {
    if (!(await exportBtn.isDisabled())) throw new Error('未定稿时导出按钮未禁用');
    console.log('PASS: 未定稿时导出 Word 按钮禁用');
  } else {
    console.log('PASS: 已定稿，导出 Word 按钮可用');
  }

  // Step 10: 使用说明卡片
  const usageCard = page.getByText('使用说明');
  if (!(await usageCard.isVisible().catch(() => false))) throw new Error('使用说明卡片不可见');
  console.log('PASS: 使用说明卡片可见');

  await page.screenshot({ path: 'e2e/screenshots/12-workpaper-page.png', fullPage: true });

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-12-workpaper-page 全部通过 ==');
}
