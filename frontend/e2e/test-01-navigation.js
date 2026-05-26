async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const PAGES = [
    { path: '/', nav: '工作台总览', titles: ['工作台总览'] },
    { path: '/files', nav: '文件管理', titles: ['文件管理'] },
    { path: '/audit-library', nav: '审核点库', titles: ['审核点库'] },
    { path: '/ai-review', nav: 'AI 审核', titles: ['AI 审查', 'AI 审核'] },
    { path: '/compare', nav: '文档对比', titles: ['文档对比'] },
  ];

  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Step 1: 验证侧边栏导航完整
  await page.goto(BASE + '/');
  await page.waitForLoadState('domcontentloaded');
  const sidebar = page.locator('aside');
  const navLinks = sidebar.locator('nav a');
  const navCount = await navLinks.count();
  if (navCount !== 5) throw new Error('侧边栏导航项数量应为 5，实际为 ' + navCount);
  for (const p of PAGES) {
    const link = sidebar.getByText(p.nav);
    if (!(await link.isVisible())) throw new Error('侧边栏缺少: ' + p.nav);
  }
  console.log('Step 1: 侧边栏 5 个导航项完整');

  // Step 2: 逐项点击导航并验证页面标题
  for (const p of PAGES) {
    await sidebar.getByText(p.nav).click();
    if (p.path === '/') {
      await page.waitForURL(/\/$/);
    } else {
      await page.waitForURL('**' + p.path);
    }
    await page.waitForLoadState('domcontentloaded');

    let titleVisible = false;
    for (const title of p.titles) {
      const titleEl = page.locator('header').getByText(title).first();
      if (await titleEl.isVisible().catch(() => false)) {
        titleVisible = true;
        break;
      }
    }
    if (!titleVisible) {
      const headerText = await page.locator('header').textContent().catch(() => '') || '';
      throw new Error(p.path + ' 页面标题不可见，header=' + headerText.slice(0, 100));
    }

    await page.screenshot({ path: 'e2e/screenshots/01-' + (p.path === '/' ? 'dashboard' : p.path.replace(/\//g, '')) + '.png', fullPage: true });
    console.log('Step 2: ' + p.nav + ' (' + p.path + ') 标题可见');
  }

  if (errors.length > 0) throw new Error('JS 错误: ' + errors.join('; '));
  console.log('PASS: 无 JS 错误');
  console.log('== test-01-navigation 全部通过 ==');
}
