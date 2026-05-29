async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F1';

  // Step 1: 进入文件管理页
  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // Step 2: 页面标题
  const title = page.locator('header').getByText('文件管理');
  if (!(await title.isVisible())) throw new Error('页面标题"文件管理"不可见');
  console.log('PASS: 页面标题可见');

  // Step 3: 上传区域
  const uploadHint = page.getByText(/拖拽.*上传|选择文件/).first();
  if (!(await uploadHint.isVisible())) throw new Error('上传区域不可见');
  console.log('PASS: 上传区域可见');

  // Step 4: 4 个统计卡片 — 验证标签和数字
  const statsLabels = ['总文件', '已就绪', '转换中', '失败'];
  for (const label of statsLabels) {
    const card = page.getByText(label).first();
    if (!(await card.isVisible())) throw new Error('统计卡片缺失: ' + label);
  }
  await page.screenshot({ path: SS + '-02-stats.png' });
  console.log('PASS: 4 个统计卡片全部可见');

  // Step 5: 搜索框
  const searchInput = page.getByPlaceholder('搜索文件名...');
  if (!(await searchInput.isVisible())) throw new Error('搜索框不可见');
  console.log('PASS: 搜索框可见');

  // Step 6: 类型筛选按钮
  for (const label of ['全部', 'PDF', 'Word']) {
    const btn = page.getByRole('button', { name: label });
    if (!(await btn.isVisible())) throw new Error('类型筛选按钮缺失: ' + label);
  }
  console.log('PASS: 类型筛选按钮（全部/PDF/Word）可见');

  // Step 7: 标签筛选入口
  const tagFilterBtn = page.getByRole('button', { name: /筛选标签/ });
  if (!(await tagFilterBtn.isVisible())) throw new Error('标签筛选按钮不可见');
  console.log('PASS: 标签筛选按钮可见');

  // Step 8: 文件表格结构 — 列头
  const expectedColumns = ['文件名', '类型', '大小', '标签', '状态', '上传时间'];
  for (const col of expectedColumns) {
    const th = page.locator('th, thead').getByText(col).first();
    if (!(await th.isVisible())) throw new Error('表格列头缺失: ' + col);
  }
  console.log('PASS: 表格列头完整（' + expectedColumns.join('/') + '）');

  // Step 9: 全选 checkbox
  const selectAllCheckbox = page.locator('thead input[type="checkbox"]');
  if (!(await selectAllCheckbox.isVisible())) throw new Error('全选 checkbox 不可见');
  console.log('PASS: 全选 checkbox 可见');

  // Step 10: 全页截图 — 供人工视觉审查
  await page.screenshot({ path: SS + '-03-full-page.png', fullPage: true });

  console.log('== files-F1-skeleton 全部通过 ==');
}
