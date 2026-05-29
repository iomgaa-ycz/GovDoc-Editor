async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL7';

  // ── Step 1: 进入审核点库页 ──
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });
  console.log('PASS: 审核点库页加载完成');

  // ── Step 2: 搜索不存在的关键词 → 空结果 ──
  console.log('Step 2: 搜索不存在的关键词');
  const searchInput = page.getByPlaceholder('搜索审查要点...');
  await searchInput.fill('ZZZXXX_绝对不存在的审查要点_12345');
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-02-search-no-match.png', fullPage: true });

  const rows = page.locator('table tbody tr');
  const rowCount = await rows.count();
  const bodyText = await page.locator('table tbody').textContent() || '';
  if (bodyText.includes('暂无') || rowCount === 0) {
    console.log('PASS: 搜索无结果显示空状态（行数: ' + rowCount + '）');
  } else {
    throw new Error('搜索无结果后未显示空状态，行数: ' + rowCount + '，内容: ' + bodyText.slice(0, 100));
  }

  // 清空搜索
  await searchInput.fill('');
  await page.waitForTimeout(500);

  // ── Step 3: 新建空库 → 验证空状态 → 删除清理 ──
  console.log('Step 3: 新建空库验证空状态');
  const libName = 'E2E空库测试' + Date.now().toString().slice(-4);

  // 点击"新建库"
  const createBtn = page.getByRole('button', { name: '新建库' });
  await createBtn.click();
  const createDialog = page.locator('[role="dialog"]');
  await createDialog.waitFor({ state: 'visible', timeout: 5000 });
  const createTitle = createDialog.getByText('新建审核点库');
  if (!(await createTitle.isVisible())) throw new Error('新建对话框标题"新建审核点库"不可见');

  // 填写名称
  const nameInput = createDialog.locator('input[placeholder="库名称"]');
  await nameInput.fill(libName);

  // 点击创建
  const confirmCreateBtn = createDialog.getByRole('button', { name: '创建' });
  await confirmCreateBtn.click();
  await page.waitForTimeout(2000);

  // 点击侧栏新库
  const sidebarEntry = page.getByText(libName).first();
  if (!(await sidebarEntry.isVisible())) throw new Error('侧栏未显示新库: ' + libName);
  await sidebarEntry.click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: SS + '-03-empty-library.png', fullPage: true });

  // 验证空状态文案
  const emptyText = await page.locator('table tbody, main').textContent() || '';
  if (emptyText.includes('暂无审核点')) {
    console.log('PASS: 空库显示"暂无审核点"提示');
  } else {
    throw new Error('空库未显示"暂无审核点"提示，内容: ' + emptyText.slice(0, 100));
  }

  // 清理：删除库
  console.log('Step 3 清理: 删除空库');
  const deleteBtn = page.getByRole('button', { name: '删除库' });
  await deleteBtn.click();
  const deleteDialog = page.locator('[role="dialog"]');
  await deleteDialog.waitFor({ state: 'visible', timeout: 5000 });
  const deleteTitle = deleteDialog.getByText('删除审核点库');
  if (!(await deleteTitle.isVisible())) throw new Error('删除对话框标题"删除审核点库"不可见');
  const confirmDeleteBtn = deleteDialog.getByRole('button', { name: '确认删除' });
  await confirmDeleteBtn.click();
  await page.waitForTimeout(2000);
  console.log('PASS: 空库已删除');

  // ── Step 4: 验证"加入库"按钮在未选择时禁用 ──
  console.log('Step 4: 验证"加入库"按钮禁用状态');
  const addToLibBtn = page.getByRole('button', { name: '加入库' });
  if (await addToLibBtn.isDisabled()) {
    console.log('PASS: 未选择审核点时"加入库"按钮已禁用');
  } else {
    throw new Error('"加入库"按钮在未选择审核点时未禁用');
  }

  // ── Step 5: 加载状态截图 ──
  console.log('Step 5: 捕获加载状态');
  await page.goto(BASE + '/audit-library');
  await page.screenshot({ path: SS + '-05-loading.png', fullPage: true });
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-06-loaded.png', fullPage: true });
  console.log('PASS: 加载状态截图已保存');

  console.log('== audit-AL7-empty-state 全部通过 ==');
}
