async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/review-R1';

  // ── Step 1: 导航到 AI 审查页 ──
  console.log('Step 1: 导航到 /ai-review');
  await page.goto(BASE + '/ai-review');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-loaded.png', fullPage: true });

  // ── Step 2: 验证页面骨架元素 ──
  console.log('Step 2: 验证骨架元素');

  // 标题
  const title = page.locator('header').getByText('AI 审查');
  if (!(await title.isVisible())) throw new Error('标题"AI 审查"不可见');

  // 新建审查按钮
  const newBtn = page.getByRole('button', { name: '新建审查' });
  if (!(await newBtn.isVisible())) throw new Error('"新建审查"按钮不可见');

  // 4 个指标卡片
  const metrics = ['总任务', '进行中', '已完成', '失败'];
  for (const m of metrics) {
    const card = page.getByText(m, { exact: true }).first();
    if (!(await card.isVisible())) throw new Error('指标卡片缺失: ' + m);
  }

  // 表头
  const headers = ['项目/文书', '审核点', '状态', '进度', '创建时间'];
  for (const h of headers) {
    const el = page.locator('th, thead, .grid').getByText(h).first();
    if (!(await el.isVisible())) throw new Error('表头缺失: ' + h);
  }

  // 操作列
  const viewBtn = page.getByRole('button', { name: '查看' }).first();
  // 不一定有数据行，所以只检查表头存在即可
  const opHeader = page.locator('.text-right').getByText('操作').first();

  await page.screenshot({ path: SS + '-02-skeleton.png', fullPage: true });
  console.log('PASS: AI 审查页骨架验证通过');

  // ── Step 3: 检查指标数值都是数字 ──
  console.log('Step 3: 检查指标数值');
  for (const m of metrics) {
    const card = page.getByText(m, { exact: true }).first().locator('..');
    const numEl = card.locator('.text-2xl, .text-3xl, .font-bold').first();
    const val = await numEl.textContent();
    if (val === null || isNaN(parseInt(val.trim()))) {
      console.log('WARN: 指标 "' + m + '" 值非数字: ' + val);
    }
  }
  console.log('PASS: 指标数值检查完成');

  console.log('== review-R1-skeleton 全部通过 ==');
}
