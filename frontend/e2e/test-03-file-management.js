async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');

  // Step 1: 进入文件管理页
  await page.goto(BASE + '/files');
  await page.waitForLoadState('domcontentloaded');
  console.log('Step 1: 进入文件管理页');
  await page.locator('header').getByText('文件管理').waitFor({ timeout: 10000 });

  // Step 2: 验证上传区
  const uploadHint = page.getByText(/拖拽.*PDF.*Word.*上传/).first();
  await uploadHint.waitFor({ timeout: 10000 });
  console.log('Step 2: 上传区可见');

  // Step 3: 验证统计卡片
  for (const label of ['总文件', '已就绪', '转换中', '失败']) {
    await page.getByText(label).first().waitFor({ timeout: 10000 });
  }
  console.log('Step 3: 统计卡片可见');

  // Step 4: 如文件表格已有数据，验证核心列
  await page.getByText('文件名').waitFor({ timeout: 10000 });
  const tbody = page.locator('tbody');
  const bodyText = await tbody.textContent().catch(() => '') || '';
  const hasFileRows = bodyText.trim() !== ''
    && !bodyText.includes('正在加载文件')
    && !bodyText.includes('没有匹配的文件')
    && !bodyText.includes('暂无');
  if (hasFileRows) {
    for (const column of ['文件名', '类型', '状态']) {
      await page.getByText(column).first().waitFor({ timeout: 10000 });
    }
    console.log('Step 4: 文件表格列可见');
  } else {
    console.log('Step 4: 文件库为空，跳过文件行列验证');
  }

  // Step 5: 测试搜索框过滤，不断言具体结果数
  const searchInput = page.getByPlaceholder('搜索文件名...').first();
  await searchInput.fill('pdf');
  if ((await searchInput.inputValue()) !== 'pdf') throw new Error('搜索框输入失败');
  await page.waitForTimeout(300);
  await searchInput.fill('');
  console.log('Step 5: 搜索框过滤无报错');

  // Step 6: 测试类型筛选按钮
  for (const label of ['全部', 'PDF', 'Word']) {
    await page.getByRole('button', { name: label }).click();
    await page.waitForTimeout(200);
  }
  console.log('Step 6: 类型筛选按钮无报错');

  await page.screenshot({ path: 'e2e/screenshots/03-file-management.png', fullPage: true });
  console.log('== test-03-file-management 全部通过 ==');
}
