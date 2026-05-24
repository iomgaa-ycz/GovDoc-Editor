async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 进入首页，等待数据加载
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  const firstRow = page.locator('table tbody tr').first();
  await firstRow.waitFor({ timeout: 15000 });
  console.log('Step 1: Dashboard 数据加载完成');

  // Step 2: 验证 4 个 MetricCard
  const labels = ['审核要点', '完成审核', '发现问题', '工作底稿'];
  for (const label of labels) {
    const card = page.getByText(label).first();
    if (!(await card.isVisible())) throw new Error('MetricCard 缺失: ' + label);
  }
  console.log('PASS: 4 个 MetricCard 全部显示');

  // Step 3: "创建审查任务" 按钮跳转
  const createBtn = page.getByRole('link', { name: /创建审查任务/ });
  if (!(await createBtn.isVisible())) throw new Error('"创建审查任务" 按钮不存在');
  await createBtn.click();
  await page.waitForURL('**/ai-review', { timeout: 10000 });
  console.log('PASS: "创建审查任务" 跳转到 /ai-review');

  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  await firstRow.waitFor({ timeout: 15000 });

  // Step 4: 表格行数据完整性
  const rows = page.locator('table tbody tr');
  const rowCount = await rows.count();
  if (rowCount < 1) throw new Error('表格行为空');

  const firstCells = rows.first().locator('td');
  const cellCount = await firstCells.count();
  if (cellCount < 4) throw new Error('表格列数不足: ' + cellCount);

  const projName = (await firstCells.nth(0).textContent() || '').trim();
  if (!projName) throw new Error('第一行项目名称为空');

  const statusCell = firstCells.nth(3);
  const statusText = (await statusCell.textContent() || '').trim();
  const validStatuses = ['未开始', '审查中', '已完成'];
  if (!validStatuses.some(s => statusText.includes(s))) {
    throw new Error('状态 Badge 异常: ' + statusText);
  }
  console.log('PASS: 表格行数据完整（' + rowCount + ' 行），首行项目: ' + projName);

  // Step 5: "审查情况" 卡片
  const summaryCard = page.getByText('审查情况').first();
  if (!(await summaryCard.isVisible())) throw new Error('"审查情况" 卡片不可见');
  console.log('PASS: "审查情况" 卡片可见');

  await page.screenshot({ path: 'e2e/screenshots/08-dashboard-details.png', fullPage: true });

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('== test-08-dashboard-details 全部通过 ==');
}
