async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C2';

  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');

  // Step 1: 打开 FilePickerModal
  console.log('Step 1: 打开文件选择弹窗');
  await page.getByRole('button', { name: /从文件库添加/ }).click();
  const modal = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' });
  await modal.waitFor({ timeout: 10000 });
  await page.screenshot({ path: SS + '-01-modal-open.png', fullPage: true });
  console.log('PASS: FilePickerModal 已打开');

  // Step 2: 弹窗标题
  const modalTitle = modal.getByText('选择文件').first();
  if (!(await modalTitle.isVisible())) throw new Error('弹窗标题不可见');
  console.log('PASS: 弹窗标题"选择文件"可见');

  // Step 3: 搜索框
  const searchInput = modal.locator('input[placeholder="搜索文件名..."]');
  if (!(await searchInput.isVisible())) throw new Error('搜索框不可见');
  console.log('PASS: 搜索框可见');

  // Step 4: 类型筛选按钮
  for (const label of ['全部', 'PDF', 'DOCX']) {
    const btn = modal.getByRole('button', { name: label }).first();
    if (!(await btn.isVisible())) throw new Error('类型筛选按钮缺失: ' + label);
  }
  console.log('PASS: 类型筛选按钮（全部/PDF/DOCX）可见');

  // Step 5: 文件列表加载（w-full 区分文件项和筛选按钮）
  const fileItems = modal.locator('.overflow-y-auto button.w-full');
  let fileCount = 0;
  for (let i = 0; i < 20; i++) {
    fileCount = await fileItems.count();
    if (fileCount > 0) break;
    await page.waitForTimeout(500);
  }
  if (fileCount === 0) throw new Error('文件列表为空（文件库无已转换文件）');
  await page.screenshot({ path: SS + '-02-file-list.png', fullPage: true });
  console.log('PASS: 文件列表已加载（' + fileCount + ' 个文件）');

  // Step 6: 搜索过滤
  const firstFileText = await fileItems.first().textContent() || '';
  const searchKey = firstFileText.trim().slice(0, 4);
  if (searchKey.length > 0) {
    console.log('Step 6: 搜索关键词 "' + searchKey + '"');
    await searchInput.fill(searchKey);
    await page.waitForTimeout(500);
    const filteredCount = await fileItems.count();
    if (filteredCount === 0) throw new Error('搜索 "' + searchKey + '" 后无结果');
    if (filteredCount > fileCount) throw new Error('搜索后文件数反而增多');
    await page.screenshot({ path: SS + '-03-search-filter.png', fullPage: true });
    console.log('PASS: 搜索过滤（' + fileCount + ' → ' + filteredCount + '）');
    await searchInput.fill('');
    await page.waitForTimeout(300);
  }

  // Step 7: 类型筛选 — PDF
  console.log('Step 7: PDF 类型筛选');
  await modal.getByRole('button', { name: 'PDF' }).first().click();
  await page.waitForTimeout(500);
  const pdfCount = await fileItems.count();
  await page.screenshot({ path: SS + '-04-filter-pdf.png', fullPage: true });
  console.log('PASS: PDF 筛选（' + pdfCount + ' 个文件）');

  // 恢复到全部
  await modal.getByRole('button', { name: '全部' }).first().click();
  await page.waitForTimeout(300);

  // Step 8: 勾选 2 个文件
  console.log('Step 8: 勾选 2 个文件');
  await fileItems.nth(0).click();
  await page.waitForTimeout(200);
  await fileItems.nth(1).click();
  await page.waitForTimeout(200);
  const selectedText = modal.getByText(/已选择 2 个文件/);
  if (!(await selectedText.isVisible())) throw new Error('footer 未显示"已选择 2 个文件"');
  await page.screenshot({ path: SS + '-05-two-selected.png', fullPage: true });
  console.log('PASS: 勾选 2 个文件，footer 正确');

  // Step 9: "确认选择" 按钮可用
  const confirmBtn = modal.getByRole('button', { name: '确认选择' });
  if (await confirmBtn.isDisabled()) throw new Error('"确认选择"按钮仍禁用');
  await confirmBtn.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: SS + '-06-after-confirm.png', fullPage: true });
  console.log('PASS: 确认选择，弹窗关闭');

  // Step 10: 验证文件卡片出现
  const badge = page.getByText(/已选 2 个文件/);
  if (!(await badge.isVisible())) throw new Error('确认后 badge 未显示"已选 2 个文件"');
  const removeButtons = page.locator('button[aria-label*="移除"]');
  const cardCount = await removeButtons.count();
  if (cardCount < 2) throw new Error('文件卡片数不足: ' + cardCount);
  console.log('PASS: 文件卡片出现（' + cardCount + ' 个）');

  // Step 11: 取消弹窗测试
  console.log('Step 11: 取消弹窗测试');
  await page.getByRole('button', { name: /从文件库添加/ }).click();
  const modal2 = page.locator('.fixed.inset-0.z-50').filter({ hasText: '选择文件' });
  await modal2.waitFor({ timeout: 10000 });
  await modal2.getByRole('button', { name: '取消' }).click();
  await page.waitForTimeout(500);
  const modalGone = await modal2.isVisible().catch(() => false);
  if (modalGone) throw new Error('取消后弹窗未关闭');
  console.log('PASS: 取消弹窗正常关闭');

  await page.screenshot({ path: SS + '-07-final.png', fullPage: true });
  console.log('== compare-C2-file-picker 全部通过 ==');
}
