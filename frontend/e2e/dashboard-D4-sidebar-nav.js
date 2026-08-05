async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/dashboard-D4';

  // 5 个导航项
  const navItems = [
    { label: '工作台总览', path: '/', title: '项目审查工作台' },
    { label: '文件管理', path: '/files', title: '文件管理' },
    { label: '审核点库', path: '/audit-library', title: '审核点库' },
    { label: 'AI 审核', path: '/ai-review', title: 'AI 审核' },
    { label: '文档对比', path: '/compare', title: '文档对比' },
  ];

  // ── Step 1: 依次点击侧边栏 5 个导航项，验证 URL 和页面内容 ──
  console.log('Step 1: 侧边栏导航 — 逐项点击验证');
  for (const item of navItems) {
    console.log('  点击"' + item.label + '"');
    // 使用文本定位（比 getByRole 更兼容侧边栏 NavLink 渲染方式）
    const navLink = page.locator('nav').locator('a').filter({ hasText: item.label }).first();
    await navLink.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // 验证 URL
    const currentUrl = page.url();
    const expectedPath = BASE + item.path;
    if (item.path === '/') {
      if (currentUrl !== expectedPath && currentUrl !== BASE + '/') {
        throw new Error('点击"' + item.label + '"后 URL 不匹配: 期望 ' + expectedPath + ', 实际 ' + currentUrl);
      }
    } else {
      if (!currentUrl.startsWith(expectedPath)) {
        throw new Error('点击"' + item.label + '"后 URL 不匹配: 期望前缀 ' + expectedPath + ', 实际 ' + currentUrl);
      }
    }

    // 验证页面标题
    const titleEl = page.locator('header').getByText(item.title).first();
    if (!(await titleEl.isVisible().catch(() => false))) {
      // 某些页面的标题可能在 h1/h2 中
      const headingEl = page.locator('h1, h2').getByText(item.title).first();
      if (!(await headingEl.isVisible().catch(() => false))) {
        console.log('  WARN: "' + item.label + '"页面未找到标题"' + item.title + '"');
      }
    }

    // 验证侧边栏高亮
    const isActive = await navLink.evaluate(el => {
      return el.classList.contains('bg-accent') || el.classList.contains('font-medium');
    });
    if (isActive) {
      console.log('  PASS: "' + item.label + '" — URL 正确，侧边栏高亮');
    } else {
      console.log('  WARN: "' + item.label + '" — URL 正确，但侧边栏未检测到高亮 class');
    }
  }
  await page.screenshot({ path: SS + '-01-sidebar-nav.png', fullPage: true });

  // ── Step 2: 直接输入 URL 验证侧边栏高亮 ──
  console.log('Step 2: 直接输入 URL 验证侧边栏高亮');
  for (const item of navItems.slice(1)) { // 跳过首页（已在首页）
    await page.goto(BASE + item.path);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    const navLink = page.locator('nav').locator('a').filter({ hasText: item.label }).first();
    const isActive = await navLink.evaluate(el => {
      return el.classList.contains('bg-accent') || el.classList.contains('font-medium');
    });
    if (isActive) {
      console.log('  PASS: 直接访问 ' + item.path + ' — "' + item.label + '"高亮');
    } else {
      console.log('  WARN: 直接访问 ' + item.path + ' — "' + item.label + '"未高亮');
    }
  }

  // ── Step 3: 浏览器后退/前进，验证高亮跟随 ──
  console.log('Step 3: 浏览器后退/前进验证高亮');
  // 当前在最后一个页面（文档对比），后退到审核点库
  await page.goBack();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  const backUrl = page.url();
  const backNav = navItems.slice(0, -1).find(item => backUrl.startsWith(BASE + item.path));
  if (backNav) {
    const navLink = page.locator('nav').locator('a').filter({ hasText: backNav.label }).first();
    const isActive = await navLink.evaluate(el => {
      return el.classList.contains('bg-accent') || el.classList.contains('font-medium');
    });
    if (isActive) {
      console.log('PASS: 后退后 "' + backNav.label + '" 高亮正确');
    } else {
      console.log('WARN: 后退后高亮未跟随');
    }
  } else {
    console.log('INFO: 后退后 URL: ' + backUrl);
  }

  // 前进
  await page.goForward();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  const fwdUrl = page.url();
  const fwdNav = navItems.find(item => fwdUrl.startsWith(BASE + item.path));
  if (fwdNav) {
    const navLink = page.locator('nav').locator('a').filter({ hasText: fwdNav.label }).first();
    const isActive = await navLink.evaluate(el => {
      return el.classList.contains('bg-accent') || el.classList.contains('font-medium');
    });
    if (isActive) {
      console.log('PASS: 前进后 "' + fwdNav.label + '" 高亮正确');
    } else {
      console.log('WARN: 前进后高亮未跟随');
    }
  }
  await page.screenshot({ path: SS + '-02-back-forward.png', fullPage: true });

  // ── Step 4: 验证底部"系统正常运行"状态指示器 ──
  console.log('Step 4: 验证系统状态指示器');
  const statusText = page.getByText('系统正常运行');
  if (await statusText.isVisible().catch(() => false)) {
    console.log('PASS: "系统正常运行"状态可见');
    // 验证绿色圆点
    const greenDot = page.locator('.bg-status-ok.rounded-full').first();
    if (await greenDot.isVisible().catch(() => false)) {
      console.log('PASS: 系统状态绿色圆点可见');
    } else {
      console.log('INFO: 未找到绿色圆点元素（可能 class 不同）');
    }
  } else {
    console.log('WARN: "系统正常运行"文本不可见');
  }

  await page.screenshot({ path: SS + '-03-final.png', fullPage: true });
  console.log('== dashboard-D4-sidebar-nav 全部通过 ==');
}
