async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C1';

  // Step 1: 进入文档对比页
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // Step 2: 页面标题
  const title = page.getByText('文档对比').first();
  if (!(await title.isVisible())) throw new Error('页面标题"文档对比"不可见');
  console.log('PASS: 页面标题可见');

  // Step 3: 副标题
  const subtitle = page.getByText('从文件库选择已转换文件').first();
  if (!(await subtitle.isVisible())) throw new Error('副标题不可见');
  console.log('PASS: 副标题可见');

  // Step 4: "新建对比任务" 卡片
  const newTaskCard = page.getByText('新建对比任务').first();
  if (!(await newTaskCard.isVisible())) throw new Error('"新建对比任务"卡片不可见');
  console.log('PASS: 新建对比任务卡片可见');

  // Step 5: 空状态引导
  const emptyHint = page.getByText('从文件库选择已转换完成的文件').first();
  if (!(await emptyHint.isVisible())) throw new Error('空状态引导文字不可见');
  console.log('PASS: 空状态引导文字可见');

  // Step 6: "从文件库添加" 按钮
  const addBtn = page.getByRole('button', { name: /从文件库添加/ });
  if (!(await addBtn.isVisible())) throw new Error('"从文件库添加"按钮不可见');
  console.log('PASS: "从文件库添加"按钮可见');

  // Step 7: "开始对比" 按钮 — 初始禁用
  const compareBtn = page.getByRole('button', { name: /开始对比/ });
  if (!(await compareBtn.isVisible())) throw new Error('"开始对比"按钮不可见');
  if (!(await compareBtn.isDisabled())) throw new Error('"开始对比"按钮初始未禁用');
  console.log('PASS: "开始对比"按钮可见且初始禁用');

  // Step 8: "历史对比" 区域
  const historyTitle = page.getByText('历史对比').first();
  if (!(await historyTitle.isVisible())) throw new Error('"历史对比"区域不可见');
  console.log('PASS: "历史对比"区域可见');

  // Step 9: 历史表头
  const headers = ['文件', '状态', '匹配数', '创建时间', '操作'];
  for (const h of headers) {
    const el = page.getByText(h).first();
    if (!(await el.isVisible())) throw new Error('历史表头缺失: ' + h);
  }
  console.log('PASS: 历史表头完整（' + headers.join('/') + '）');

  // Step 10: 全页截图
  await page.screenshot({ path: SS + '-02-full-page.png', fullPage: true });

  console.log('== compare-C1-skeleton 全部通过 ==');
}
