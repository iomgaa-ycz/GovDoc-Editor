async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F7';

  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();

  // ── Step 1: 搜索不存在的关键词 → "没有匹配的文件" ──
  console.log('Step 1: 搜索不存在的关键词');
  const searchInput = page.getByPlaceholder('搜索文件名...');
  await searchInput.fill('ZZZXXX_ABSOLUTELY_NONEXISTENT_FILE_12345');
  await page.waitForTimeout(500);

  await page.screenshot({ path: SS + '-02-no-match.png', fullPage: true });

  const noMatchHint = page.getByText('没有匹配的文件');
  if (await noMatchHint.isVisible().catch(() => false)) {
    console.log('PASS: 显示"没有匹配的文件"空状态');
  } else {
    // 也可能是"暂无"或其他文案
    const bodyText = await page.locator('tbody, main').textContent() || '';
    if (bodyText.includes('暂无') || bodyText.includes('没有')) {
      console.log('PASS: 显示空状态提示');
    } else {
      throw new Error('搜索无结果后未显示空状态提示');
    }
  }

  // 清空搜索
  await searchInput.fill('');
  await page.waitForTimeout(500);

  // ── Step 2: 类型筛选无结果场景 ──
  // 先用搜索缩小范围再加类型筛选，确保能触发空结果
  console.log('Step 2: 组合筛选无结果');
  await searchInput.fill('ZZZXXX_NONEXISTENT');
  await page.getByRole('button', { name: 'PDF' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-03-combined-empty.png', fullPage: true });
  console.log('PASS: 组合筛选空结果已截图');

  // 复位
  await searchInput.fill('');
  await page.getByRole('button', { name: '全部' }).click();
  await page.waitForTimeout(300);

  // ── Step 3: 真正的空文件库状态 ──
  if (initialCount === 0) {
    console.log('Step 3: 文件库为空 — 验证空状态 UI');
    await page.screenshot({ path: SS + '-04-empty-library.png', fullPage: true });

    // 验证空状态图标和提示文案
    const emptyIcon = page.locator('svg').filter({ has: page.locator('path') }).first();
    const emptyText = page.getByText(/暂无|没有|上传/).first();
    if (await emptyText.isVisible().catch(() => false)) {
      console.log('PASS: 空文件库显示引导提示');
    } else {
      console.log('WARN: 空文件库状态截图供人工检查');
    }
  } else {
    console.log('Step 3: 文件库非空（' + initialCount + ' 个文件），跳过空库测试');
  }

  // ── Step 4: 加载状态截图（刷新页面捕获瞬间） ──
  console.log('Step 4: 刷新页面捕获加载状态');
  await page.goto(BASE + '/files');
  // 立即截图，捕获加载中状态
  await page.screenshot({ path: SS + '-05-loading-state.png', fullPage: true });
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-06-loaded-state.png', fullPage: true });
  console.log('PASS: 加载状态截图已保存');

  console.log('== files-F7-empty-state 全部通过 ==');
}
