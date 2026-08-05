async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL6';
  const libName = 'E2E关联测试库' + Date.now().toString().slice(-4);

  // ── Step 1: 导航到审核点库页面，检查前置数据 ──
  console.log('Step 1: 导航到 /audit-library');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  const rowCount = await page.locator('table tbody tr').count();
  if (rowCount < 2) {
    console.log('SKIP: 表格行数不足 2（当前 ' + rowCount + ' 行），需要 AL2 导入数据');
    return;
  }
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });
  console.log('PASS: 审核点库页面加载完成，共 ' + rowCount + ' 行');

  // ── Step 2: 选择前 2 个审核点 ──
  console.log('Step 2: 选择 2 个审核点');
  const row0Checkbox = page.locator('table tbody tr').nth(0).locator('input[type="checkbox"]');
  await row0Checkbox.click();
  await page.waitForTimeout(200);

  const row1Checkbox = page.locator('table tbody tr').nth(1).locator('input[type="checkbox"]');
  await row1Checkbox.click();
  await page.waitForTimeout(200);

  const selectedBadge = page.getByText('已选择 2');
  if (!(await selectedBadge.isVisible())) throw new Error('"已选择 2" 徽标不可见');
  await page.screenshot({ path: SS + '-02-two-selected.png', fullPage: true });
  console.log('PASS: 已选择 2 个审核点，徽标可见');

  // ── Step 3: 打开"加入库"对话框 ──
  console.log('Step 3: 打开"加入库"对话框');
  const addToLibBtn = page.getByRole('button', { name: '加入库' });
  await addToLibBtn.click();

  const dialog = page.locator('[role="dialog"]');
  await dialog.waitFor({ state: 'visible', timeout: 5000 });
  const dialogTitle = dialog.getByText('加入审核点库');
  if (!(await dialogTitle.isVisible())) throw new Error('对话框标题"加入审核点库"不可见');
  await page.screenshot({ path: SS + '-03-add-dialog.png', fullPage: true });
  console.log('PASS: "加入审核点库"对话框已打开');

  // ── Step 4: 内联创建新库并确认 ──
  console.log('Step 4: 内联创建新库"' + libName + '"');
  const newLibInput = dialog.locator('input[placeholder*="新库名称"]');
  await newLibInput.fill(libName);
  await page.screenshot({ path: SS + '-04-new-lib-name.png', fullPage: true });

  const confirmAddBtn = dialog.getByRole('button', { name: '确认加入' });
  await confirmAddBtn.click();
  await page.waitForTimeout(3000);

  // 验证对话框关闭
  if (await dialog.isVisible()) throw new Error('"加入库"对话框未关闭');
  console.log('PASS: 确认加入后对话框已关闭');

  // ── Step 5: 切换到新库视图 ──
  console.log('Step 5: 切换到新库"' + libName + '"');
  const sidebarEntry = page.getByText(libName).first();
  await sidebarEntry.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-05-new-lib-view.png', fullPage: true });

  const libRowCount = await page.locator('table tbody tr').count();
  if (libRowCount < 2) throw new Error('新库中行数不足 2（当前 ' + libRowCount + ' 行）');
  console.log('PASS: 新库视图显示 ' + libRowCount + ' 行数据');

  // ── Step 6: 移出当前库 ──
  console.log('Step 6: 从库中移出第 1 个审核点');
  const firstRowCheckbox = page.locator('table tbody tr').nth(0).locator('input[type="checkbox"]');
  await firstRowCheckbox.click();
  await page.waitForTimeout(200);

  const removeBtn = page.getByRole('button', { name: '移出当前库' });
  await removeBtn.click();

  // 轮询等待行数减少（后端异步移出 + 前端刷新需要时间）
  await page.waitForFunction(
    (expectedCount) => document.querySelectorAll('table tbody tr').length < expectedCount,
    libRowCount,
    { timeout: 10000, polling: 500 }
  );
  await page.screenshot({ path: SS + '-06-after-remove.png', fullPage: true });

  const afterRemoveCount = await page.locator('table tbody tr').count();
  if (afterRemoveCount >= libRowCount) throw new Error('移出后行数未减少（之前 ' + libRowCount + '，现在 ' + afterRemoveCount + '）');
  console.log('PASS: 移出成功，行数从 ' + libRowCount + ' 减至 ' + afterRemoveCount);

  // ── Step 7: 清理——删除测试库 ──
  console.log('Step 7: 清理——删除测试库');
  const deleteBtn = page.getByRole('button', { name: '删除库' });
  await deleteBtn.click();

  const deleteDialog = page.locator('[role="dialog"]');
  await deleteDialog.waitFor({ state: 'visible', timeout: 5000 });
  const deleteTitle = deleteDialog.getByText('删除审核点库');
  if (!(await deleteTitle.isVisible())) throw new Error('删除对话框标题"删除审核点库"不可见');

  const confirmDeleteBtn = deleteDialog.getByRole('button', { name: '确认删除' });
  await confirmDeleteBtn.click();
  await page.waitForTimeout(2000);

  const allPointsHeading = page.locator('h2').getByText('全部审核点');
  if (!(await allPointsHeading.isVisible())) throw new Error('删除后未回到"全部审核点"视图');
  await page.screenshot({ path: SS + '-07-after-cleanup.png', fullPage: true });
  console.log('PASS: 测试库已删除，回到"全部审核点"视图');

  console.log('== audit-AL6-library-membership 全部通过 ==');
}
