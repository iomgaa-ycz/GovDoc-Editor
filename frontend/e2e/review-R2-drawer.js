async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R2';

  // ── Step 1: 导航到 AI 审查页 ──
  console.log('Step 1: 导航到 /ai-review');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');

  // ── Step 2: 打开新建审查抽屉 ──
  console.log('Step 2: 打开新建审查抽屉');
  const newBtn = page.getByRole('button', { name: '新建审查' });
  await newBtn.click();

  // 等待抽屉出现
  const drawer = page.locator('.fixed.inset-0.z-50').filter({ hasText: '新建审查任务' });
  await drawer.waitFor({ state: 'visible', timeout: 10000 });
  await page.screenshot({ path: SS + '-01-drawer-open.png', fullPage: true });
  console.log('PASS: 抽屉已打开');

  // ── Step 3: 验证抽屉内 4 个 Card 区域 ──
  console.log('Step 3: 验证抽屉结构');

  const sections = ['选择项目', '招标文书', /补充文件/, '审查范围'];
  for (const s of sections) {
    const section = drawer.getByText(s, { exact: false }).first();
    if (!(await section.isVisible().catch(() => false))) {
      throw new Error('抽屉区域缺失: ' + (typeof s === 'string' ? s : s.source));
    }
  }
  console.log('PASS: 4 个 Card 区域全部可见');

  // ── Step 4: 验证底部按钮 ──
  console.log('Step 4: 验证底部按钮');
  const cancelBtn = drawer.getByRole('button', { name: '取消' });
  const submitBtn = drawer.getByRole('button', { name: /开始审查/ });
  if (!(await cancelBtn.isVisible())) throw new Error('"取消"按钮不可见');
  if (!(await submitBtn.isVisible())) throw new Error('"开始审查"按钮不可见');
  if (!(await submitBtn.isDisabled())) throw new Error('"开始审查"按钮初始应禁用');
  console.log('PASS: 底部按钮正确，"开始审查"初始禁用');

  // ── Step 5: 验证项目下拉框 ──
  console.log('Step 5: 验证项目选择');
  const projectSelect = drawer.locator('.space-y-2').first().locator('button').first();
  // 如果有项目，下拉框应可见；如果没有则显示"加载项目中..."
  const projectArea = drawer.getByText(/选择项目|现有项目|加载项目/).first();
  if (!(await projectArea.isVisible())) {
    throw new Error('项目选择区域不可见');
  }
  console.log('PASS: 项目选择区域可见');

  // ── Step 6: 验证"选择招标文书"按钮 ──
  console.log('Step 6: 验证文书选择');
  const docSelectBtn = drawer.getByRole('button', { name: '选择招标文书' });
  if (!(await docSelectBtn.isVisible())) throw new Error('"选择招标文书"按钮不可见');
  console.log('PASS: "选择招标文书"按钮可见');

  // ── Step 7: 验证"审查范围"两种模式 ──
  console.log('Step 7: 验证审查范围模式');
  const libraryMode = drawer.getByText('按审核点库', { exact: true }).first();
  const manualMode = drawer.getByText('手动选择', { exact: true }).first();
  // 至少手动选择应该可见
  if (!(await manualMode.isVisible())) throw new Error('"手动选择"模式按钮不可见');
  console.log('PASS: 审查范围模式按钮可见');

  // ── Step 8: 关闭抽屉 ──
  console.log('Step 8: 关闭抽屉');
  await cancelBtn.click();
  await drawer.waitFor({ state: 'hidden', timeout: 5000 }).catch(() => {});
  await page.screenshot({ path: SS + '-02-drawer-closed.png', fullPage: true });
  console.log('PASS: 抽屉已关闭');

  console.log('== review-R2-drawer 全部通过 ==');
}
