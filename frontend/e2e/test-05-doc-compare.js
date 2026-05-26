async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');

  // Step 1: 进入文档对比页
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入文档对比页');
  await page.getByText('新建对比任务').first().waitFor({ timeout: 10000 });

  // Step 2: 验证文件库选择入口
  const openPickerBtn = page.getByRole('button', { name: /从文件库(添加|选择文件)/ }).first();
  await openPickerBtn.waitFor({ timeout: 10000 });
  console.log('Step 2: 文件库选择入口可见');

  // Step 3: 打开 FilePickerModal
  await openPickerBtn.click();
  const modal = page.locator('.fixed.inset-0.z-50.flex.items-center.justify-center').filter({ hasText: '选择文件' }).first();
  await modal.getByText('选择文件').waitFor({ timeout: 10000 });
  console.log('Step 3: FilePickerModal 已弹出');

  // Step 4: 如果文件库有文件，选择 2 个并确认
  const fileRows = modal.locator('div.flex-1.overflow-y-auto button');
  let fileCount = 0;
  for (let i = 0; i < 10; i++) {
    fileCount = await fileRows.count();
    if (fileCount > 0) break;
    await page.waitForTimeout(500);
  }
  if (fileCount >= 2) {
    await fileRows.nth(0).click();
    await fileRows.nth(1).click();
    await modal.getByRole('button', { name: '确认选择' }).click();
    await page.locator('header').getByText('文档对比').waitFor({ timeout: 10000 });
    await page.locator('main').getByText(/已选 2 个文件/).waitFor({ timeout: 10000 });
    const selectedCards = page.locator('main button[aria-label^="移除 "]');
    const selectedCount = await selectedCards.count();
    if (selectedCount < 2) throw new Error('选中文件卡片不足: ' + selectedCount);
    console.log('Step 4: 已选择 2 个文件并显示文件卡片');
  } else {
    await modal.getByRole('button', { name: '取消' }).click();
    await modal.getByText('选择文件').waitFor({ state: 'hidden', timeout: 10000 });
    console.log('Step 4: 文件库少于 2 个文件，跳过选择分支');
  }

  // Step 5: 验证开始对比按钮存在
  await page.getByRole('button', { name: /开始对比/ }).waitFor({ timeout: 10000 });
  console.log('Step 5: 开始对比按钮存在');

  // Step 6: 验证历史对比表格区域存在
  await page.getByText('历史对比').waitFor({ timeout: 10000 });
  await page.getByText('匹配数').waitFor({ timeout: 10000 });
  console.log('Step 6: 历史对比区域存在');

  // Step 7: 验证取消/关闭弹窗不报错
  const reopenBtn = page.getByRole('button', { name: /从文件库(添加|选择文件)/ }).first();
  await reopenBtn.click();
  const reopenedModal = page.locator('.fixed.inset-0.z-50.flex.items-center.justify-center').filter({ hasText: '选择文件' }).first();
  await reopenedModal.getByText('选择文件').waitFor({ timeout: 10000 });
  await reopenedModal.getByRole('button', { name: '取消' }).click();
  await reopenedModal.getByText('选择文件').waitFor({ state: 'hidden', timeout: 10000 });
  console.log('Step 7: 取消弹窗无报错');

  await page.screenshot({ path: 'e2e/screenshots/05-doc-compare.png', fullPage: true });
  console.log('== test-05-doc-compare 全部通过 ==');
}
