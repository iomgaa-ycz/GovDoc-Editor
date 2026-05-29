async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/dashboard-D1';

  // Step 1: 进入工作台总览页
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // Step 2: header 标题 "工作台总览"
  const headerTitle = page.locator('header').getByText('工作台总览');
  if (!(await headerTitle.isVisible())) throw new Error('header 标题"工作台总览"不可见');
  console.log('PASS: header 标题可见');

  // Step 3: 页面副标题 "项目审查工作台"
  const subtitle = page.getByRole('heading', { name: '项目审查工作台' });
  if (!(await subtitle.isVisible())) throw new Error('副标题"项目审查工作台"不可见');
  console.log('PASS: 副标题可见');

  // Step 4: "创建审查任务" 按钮
  const createBtn = page.getByRole('button', { name: /创建审查任务/ });
  if (!(await createBtn.isVisible())) throw new Error('"创建审查任务"按钮不可见');
  console.log('PASS: "创建审查任务"按钮可见');

  // Step 5: 四个指标卡片标签
  const metricLabels = ['审核要点', '完成审核', '发现问题', '工作底稿'];
  for (const label of metricLabels) {
    const card = page.getByText(label, { exact: true }).first();
    if (!(await card.isVisible())) throw new Error('指标卡片缺失: ' + label);
  }
  await page.screenshot({ path: SS + '-02-metrics.png', fullPage: true });
  console.log('PASS: 4 个指标卡片标签全部可见');

  // Step 6: "近期审核记录" 卡片标题
  const recentTitle = page.getByText('近期审核记录').first();
  if (!(await recentTitle.isVisible())) throw new Error('"近期审核记录"卡片标题不可见');
  console.log('PASS: "近期审核记录"卡片标题可见');

  // Step 7: 表格列头
  const expectedColumns = ['项目名称', '审核要点', '发现问题', '状态'];
  for (const col of expectedColumns) {
    const th = page.locator('th, thead').getByText(col).first();
    if (!(await th.isVisible())) throw new Error('表格列头缺失: ' + col);
  }
  console.log('PASS: 表格列头完整（' + expectedColumns.join('/') + '）');

  // Step 8: "审查情况" 卡片标题
  const summaryTitle = page.getByText('审查情况').first();
  if (!(await summaryTitle.isVisible())) throw new Error('"审查情况"卡片标题不可见');
  console.log('PASS: "审查情况"卡片标题可见');

  // Step 9: 最终全页截图
  await page.screenshot({ path: SS + '-03-full-page.png', fullPage: true });

  console.log('== dashboard-D1-skeleton 全部通过 ==');
}
