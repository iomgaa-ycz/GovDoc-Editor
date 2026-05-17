async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const PAGES = [
    { path: '/', title: '工作台总览', content: '项目审查工作台' },
    { path: '/audit-library', title: '审核点库', content: '审核点管理' },
    { path: '/ai-review', title: 'AI 审核', content: '新建审查任务' },
    { path: '/audit-results', title: '审核结果', content: '选择审核运行' },
    { path: '/workpaper', title: '工作底稿', content: '工作底稿' },
    { path: '/compare', title: '文档对比', content: '文档对比' },
  ];

  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // 验证侧边栏导航完整
  await page.goto(BASE + '/');
  await page.waitForLoadState('domcontentloaded');
  const sidebar = page.locator('aside');
  for (const p of PAGES) {
    const link = sidebar.getByText(p.title);
    if (!(await link.isVisible())) throw new Error('侧边栏缺少: ' + p.title);
  }
  console.log('PASS: 侧边栏 6 个导航项完整');

  // 逐页导航验证
  for (const p of PAGES) {
    await page.goto(BASE + p.path);
    await page.waitForLoadState('domcontentloaded');

    // 验证 header 包含页面标题
    const header = page.locator('main').first();
    const text = await header.textContent();
    if (!text.includes(p.content)) {
      throw new Error(p.path + ' 页面缺少内容: ' + p.content + '，实际: ' + text.slice(0, 100));
    }

    // 截图
    await page.screenshot({ path: 'e2e/screenshots/01-' + p.path.replace(/\//g, '') + '.png', fullPage: true });
    console.log('PASS: ' + p.title + ' (' + p.path + ')');
  }

  // 验证导航点击切换
  await page.goto(BASE + '/');
  await sidebar.getByText('审核点库').click();
  await page.waitForURL('**/audit-library');
  await sidebar.getByText('AI 审核').click();
  await page.waitForURL('**/ai-review');
  await sidebar.getByText('文档对比').click();
  await page.waitForURL('**/compare');
  await sidebar.getByText('工作台总览').click();
  await page.waitForURL(/\/$/);
  console.log('PASS: 侧边栏导航点击切换正确');

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('PASS: 无 JS 错误');
  console.log('== test-01-navigation 全部通过 ==');
}
