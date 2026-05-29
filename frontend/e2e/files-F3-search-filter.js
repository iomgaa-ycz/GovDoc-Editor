async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/files-F3';

  await page.goto(BASE + '/files');
  await page.waitForLoadState('networkidle');

  // 前置：确保有文件数据
  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 文件库为空，无法测试搜索筛选');
    return;
  }
  console.log('初始文件数: ' + initialCount);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 1: 搜索框 — 输入已存在的文件名关键词 ──
  const firstFileName = await rows.first().locator('td').nth(1).textContent() || '';
  const searchKey = firstFileName.trim().slice(0, 4);
  console.log('Step 1: 搜索关键词 "' + searchKey + '"');

  const searchInput = page.getByPlaceholder('搜索文件名...');
  await searchInput.fill(searchKey);
  await page.waitForTimeout(500);
  const filteredCount = await rows.count();
  if (filteredCount === 0) throw new Error('搜索 "' + searchKey + '" 后无结果');
  if (filteredCount > initialCount) throw new Error('搜索后行数反而增多');
  await page.screenshot({ path: SS + '-02-search-result.png', fullPage: true });
  console.log('PASS: 搜索过滤（' + initialCount + ' → ' + filteredCount + '）');

  // ── Step 2: 清空搜索 → 恢复 ──
  await searchInput.fill('');
  await page.waitForTimeout(500);
  const restoredCount = await rows.count();
  if (restoredCount !== initialCount) {
    throw new Error('清空搜索后行数未恢复: ' + restoredCount + ' vs ' + initialCount);
  }
  console.log('PASS: 清空搜索恢复（' + restoredCount + ' 行）');

  // ── Step 3: 类型筛选 — PDF ──
  console.log('Step 3: 类型筛选');
  await page.getByRole('button', { name: 'PDF' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-03-filter-pdf.png', fullPage: true });
  const pdfCount = await rows.count();

  // 验证筛选后每行都是 PDF 类型
  for (let i = 0; i < pdfCount; i++) {
    const rowText = await rows.nth(i).textContent() || '';
    if (!rowText.includes('PDF') && !rowText.includes('pdf')) {
      throw new Error('PDF 筛选后第 ' + i + ' 行包含非 PDF 文件');
    }
  }
  console.log('PASS: PDF 筛选（' + pdfCount + ' 行，全部为 PDF）');

  // ── Step 4: 类型筛选 — Word ──
  await page.getByRole('button', { name: 'Word' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-04-filter-word.png', fullPage: true });
  const wordCount = await rows.count();
  console.log('PASS: Word 筛选（' + wordCount + ' 行）');

  // ── Step 5: 类型筛选 — 全部（恢复） ──
  await page.getByRole('button', { name: '全部' }).click();
  await page.waitForTimeout(500);
  const allCount = await rows.count();
  if (allCount !== initialCount) {
    throw new Error('点击"全部"后行数未恢复: ' + allCount + ' vs ' + initialCount);
  }
  console.log('PASS: 点击"全部"恢复（' + allCount + ' 行）');

  // ── Step 6: 类型 + 搜索组合筛选 ──
  console.log('Step 6: 组合筛选（PDF + 搜索）');
  await page.getByRole('button', { name: 'PDF' }).click();
  await page.waitForTimeout(300);
  await searchInput.fill(searchKey);
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-05-combined-filter.png', fullPage: true });
  const combinedCount = await rows.count();
  if (combinedCount > pdfCount) throw new Error('组合筛选后行数大于单独 PDF 筛选');
  console.log('PASS: 组合筛选（' + combinedCount + ' 行）');

  // 复位
  await searchInput.fill('');
  await page.getByRole('button', { name: '全部' }).click();
  await page.waitForTimeout(300);

  // ── Step 7: 全选 checkbox ──
  console.log('Step 7: 全选 checkbox');
  const selectAll = page.locator('thead input[type="checkbox"]');
  await selectAll.click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: SS + '-06-select-all.png', fullPage: true });

  // 验证 tbody 中的 checkbox 全部勾选
  const bodyCheckboxes = page.locator('tbody input[type="checkbox"]');
  const cbCount = await bodyCheckboxes.count();
  let checkedCount = 0;
  for (let i = 0; i < cbCount; i++) {
    if (await bodyCheckboxes.nth(i).isChecked()) checkedCount++;
  }
  if (checkedCount !== cbCount) {
    throw new Error('全选后只有 ' + checkedCount + '/' + cbCount + ' 行被勾选');
  }
  console.log('PASS: 全选 checkbox（' + checkedCount + '/' + cbCount + ' 已勾选）');

  // 取消全选
  await selectAll.click();
  await page.waitForTimeout(300);

  console.log('== files-F3-search-filter 全部通过 ==');
}
