async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const XLS_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/附件9 处理处罚标准.xls';
  const DOC_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc';

  // Step 1: 进入审核点库列表，等待数据
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  const rows = page.locator('table tbody tr');
  await rows.first().waitFor({ timeout: 15000 });
  const initialCount = await rows.count();
  console.log('Step 1: 审核点库加载完成，共 ' + initialCount + ' 条');

  // Step 2: 搜索框实时过滤
  const firstTitle = (await rows.first().locator('p.font-medium').first().textContent() || '').trim();
  const searchKey = firstTitle.slice(0, 3);
  const searchInput = page.getByPlaceholder('搜索审查要点...');
  await searchInput.fill(searchKey);
  await page.waitForTimeout(500);
  const filteredCount = await rows.count();
  if (filteredCount > initialCount) throw new Error('搜索后行数反而增多');
  if (filteredCount < 1) throw new Error('搜索 "' + searchKey + '" 后无结果');
  await searchInput.fill('');
  await page.waitForTimeout(500);
  const restoredCount = await rows.count();
  if (restoredCount !== initialCount) throw new Error('清空搜索后行数未恢复: ' + restoredCount + ' vs ' + initialCount);
  console.log('PASS: 搜索过滤（关键词 "' + searchKey + '"，过滤后 ' + filteredCount + ' 条，恢复 ' + restoredCount + ' 条）');

  // Step 3: 分类标签切换筛选
  const allCatBtn = page.getByText('全部分类');
  if (!(await allCatBtn.isVisible())) throw new Error('"全部分类" 标签不可见');

  const catButtons = page.locator('button.rounded-full.text-xs');
  const catCount = await catButtons.count();
  if (catCount > 1) {
    await catButtons.nth(1).click();
    await page.waitForTimeout(500);
    const catFilteredCount = await rows.count();
    if (catFilteredCount > initialCount) throw new Error('分类筛选后行数反而增多');
    await allCatBtn.click();
    await page.waitForTimeout(500);
    const catRestoredCount = await rows.count();
    if (catRestoredCount !== initialCount) throw new Error('分类恢复后行数不一致');
    console.log('PASS: 分类筛选（筛选后 ' + catFilteredCount + ' 条）');
  } else {
    console.log('SKIP: 仅一个分类，跳过分类筛选测试');
  }

  // Step 4: 编辑审核点 — 保存
  const editBtns = rows.first().locator('td').last().locator('button').first();
  await editBtns.click();

  const dialogTitle = page.getByText('编辑审查要点');
  await dialogTitle.waitFor({ timeout: 5000 });

  const titleInput = page.locator('[role="dialog"] input').first();
  const originalTitle = await titleInput.inputValue();
  await titleInput.fill(originalTitle + ' [E2E]');
  await page.getByRole('button', { name: '保存修改' }).click();

  const updatedRow = page.getByText(originalTitle + ' [E2E]');
  await updatedRow.waitFor({ timeout: 10000 });
  console.log('PASS: 编辑保存成功');

  // Step 5: 编辑 — 还原数据
  const editBtns2 = rows.first().locator('td').last().locator('button').first();
  await editBtns2.click();
  await dialogTitle.waitFor({ timeout: 5000 });
  const titleInput2 = page.locator('[role="dialog"] input').first();
  await titleInput2.fill(originalTitle);
  await page.getByRole('button', { name: '保存修改' }).click();
  await page.waitForTimeout(1000);
  console.log('PASS: 编辑还原数据');

  // Step 6: 编辑 — 取消
  const editBtns3 = rows.first().locator('td').last().locator('button').first();
  await editBtns3.click();
  await dialogTitle.waitFor({ timeout: 5000 });
  const titleInput3 = page.locator('[role="dialog"] input').first();
  await titleInput3.fill('SHOULD_NOT_SAVE_E2E');
  await page.getByRole('button', { name: '取消' }).click();
  await page.waitForTimeout(500);
  const badRow = page.getByText('SHOULD_NOT_SAVE_E2E');
  if (await badRow.isVisible().catch(() => false)) throw new Error('取消编辑后数据被保存');
  console.log('PASS: 编辑取消不影响数据');

  // Step 7: 删除 — 取消
  const beforeDeleteCount = await rows.count();
  const deleteBtns = rows.last().locator('td').last().locator('button').last();
  await deleteBtns.click();

  const deleteDialogTitle = page.getByRole('heading', { name: '确认删除' });
  await deleteDialogTitle.waitFor({ timeout: 5000 });

  const warning = page.getByText('此操作不可撤销');
  if (!(await warning.isVisible())) throw new Error('删除确认缺少不可撤销警告');

  await page.getByRole('button', { name: '取消' }).click();
  await page.waitForTimeout(500);
  const afterCancelCount = await rows.count();
  if (afterCancelCount !== beforeDeleteCount) throw new Error('取消删除后行数变化');
  console.log('PASS: 删除取消不影响数据');

  // Step 8: 删除 — 确认
  const deleteBtns2 = rows.last().locator('td').last().locator('button').last();
  await deleteBtns2.click();
  await deleteDialogTitle.waitFor({ timeout: 5000 });
  await page.getByRole('button', { name: '确认删除' }).click();
  await page.waitForTimeout(1000);
  const afterDeleteCount = await rows.count();
  if (afterDeleteCount !== beforeDeleteCount - 1) throw new Error('删除后行数未减少: ' + afterDeleteCount + ' vs ' + (beforeDeleteCount - 1));
  console.log('PASS: 删除确认成功（' + beforeDeleteCount + ' → ' + afterDeleteCount + '）');

  // Step 9: 导入模式文件移除
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('导入审查点表格').click();
  await page.waitForLoadState('domcontentloaded');

  const importFileInput = page.locator("input[type='file']");
  await importFileInput.setInputFiles(XLS_PATH);
  await page.waitForTimeout(500);
  const importFileName = page.getByText('附件9 处理处罚标准.xls');
  if (!(await importFileName.isVisible())) throw new Error('导入文件名未显示');

  const importRemoveBtn = page.getByText('移除');
  await importRemoveBtn.click();
  await page.waitForTimeout(300);
  const dropzone = page.getByText('选择审查点表格');
  if (!(await dropzone.isVisible())) throw new Error('移除后 FileDropzone 未恢复');
  console.log('PASS: 导入模式文件移除');

  await page.getByRole('button', { name: /返回列表/ }).click();
  await page.waitForLoadState('domcontentloaded');

  // Step 10: 提取模式文件移除
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByRole('menuitem', { name: 'AI 提取' }).click();
  await page.waitForLoadState('domcontentloaded');

  const extractFileInput = page.locator("input[type='file']");
  await extractFileInput.setInputFiles(DOC_PATH);
  await page.waitForTimeout(500);

  const extractRemoveBtn = page.getByText('移除');
  await extractRemoveBtn.click();
  await page.waitForTimeout(300);
  const extractDropzone = page.getByText('选择或拖入法规文件');
  if (!(await extractDropzone.isVisible())) throw new Error('移除后 FileDropzone 未恢复');
  console.log('PASS: 提取模式文件移除');

  await page.getByRole('button', { name: /返回列表/ }).click();
  await page.waitForLoadState('domcontentloaded');

  // Step 11: 空列表状态
  const searchInput2 = page.getByPlaceholder('搜索审查要点...');
  await searchInput2.fill('ZZZXXXYYY_NONEXISTENT_12345');
  await page.waitForTimeout(500);
  const emptyHint = page.getByText('暂无审核点');
  if (!(await emptyHint.isVisible())) throw new Error('空列表状态未显示');
  await searchInput2.fill('');
  console.log('PASS: 空列表状态正确显示');

  await page.screenshot({ path: 'e2e/screenshots/09-audit-library-crud.png', fullPage: true });
  console.log('== test-09-audit-library-crud 全部通过 ==');
}
