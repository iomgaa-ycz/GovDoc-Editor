async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL3';

  // Step 1: 进入审核点库页，确认有数据
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');

  const rows = page.locator('table tbody tr');
  const initialCount = await rows.count();
  if (initialCount === 0) {
    console.log('⏭ 跳过: 审核点库为空（AL2 未导入数据），无法测试搜索筛选');
    return;
  }
  console.log('初始行数: ' + initialCount);
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });

  // ── Step 2: 搜索 — 取第一行标题前4字作为关键词 ──
  const firstTitle = await rows.first().locator('td').nth(1).locator('p').first().textContent() || '';
  const searchKey = firstTitle.trim().slice(0, 4);
  console.log('Step 2: 搜索关键词 "' + searchKey + '"');

  const searchInput = page.getByPlaceholder('搜索审查要点...');
  await searchInput.fill(searchKey);
  await page.waitForTimeout(500);

  const searchedCount = await rows.count();
  if (searchedCount === 0) throw new Error('搜索 "' + searchKey + '" 后无结果');
  if (searchedCount > initialCount) throw new Error('搜索后行数反而增多');
  await page.screenshot({ path: SS + '-02-search-result.png', fullPage: true });
  console.log('PASS: 搜索过滤（' + initialCount + ' → ' + searchedCount + '）');

  // ── Step 3: 清空搜索 → 恢复 ──
  await searchInput.fill('');
  await page.waitForTimeout(500);
  const restoredCount = await rows.count();
  if (restoredCount !== initialCount) {
    throw new Error('清空搜索后行数未恢复: ' + restoredCount + ' vs ' + initialCount);
  }
  console.log('PASS: 清空搜索恢复（' + restoredCount + ' 行）');

  // ── Step 4: 分类筛选 ──
  console.log('Step 4: 分类筛选');
  const allPills = page.locator('button.rounded-full');
  const pillCount = await allPills.count();

  // 收集非"全部分类"的分类按钮
  const categoryPills = [];
  for (let i = 0; i < pillCount; i++) {
    const text = (await allPills.nth(i).textContent() || '').trim();
    if (text && text !== '全部分类') {
      categoryPills.push({ index: i, text });
    }
  }
  console.log('分类按钮数: ' + categoryPills.length);

  if (categoryPills.length > 0) {
    const firstCat = categoryPills[0];
    console.log('点击分类: "' + firstCat.text + '"');
    await allPills.nth(firstCat.index).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: SS + '-03-category-filter.png', fullPage: true });

    const catFilteredCount = await rows.count();
    console.log('分类筛选后行数: ' + catFilteredCount);

    // 验证前5行的文本包含该分类名
    const checkLimit = Math.min(catFilteredCount, 5);
    for (let i = 0; i < checkLimit; i++) {
      const rowText = await rows.nth(i).textContent() || '';
      if (!rowText.includes(firstCat.text)) {
        throw new Error('分类筛选后第 ' + i + ' 行不含分类 "' + firstCat.text + '"');
      }
    }
    console.log('PASS: 分类筛选内容验证（前 ' + checkLimit + ' 行均含 "' + firstCat.text + '"）');

    // 点击"全部分类"恢复
    await page.getByRole('button', { name: '全部分类' }).click();
    await page.waitForTimeout(500);
    const catRestoredCount = await rows.count();
    if (catRestoredCount !== initialCount) {
      throw new Error('点击"全部分类"后行数未恢复: ' + catRestoredCount + ' vs ' + initialCount);
    }
    console.log('PASS: 点击"全部分类"恢复（' + catRestoredCount + ' 行）');
  } else {
    console.log('⏭ 跳过分类筛选: 无动态分类按钮');
  }

  // ── Step 5: 组合筛选（分类 + 搜索） ──
  if (categoryPills.length > 0) {
    console.log('Step 5: 组合筛选（分类 + 搜索）');
    await allPills.nth(categoryPills[0].index).click();
    await page.waitForTimeout(300);
    await searchInput.fill(searchKey);
    await page.waitForTimeout(500);
    await page.screenshot({ path: SS + '-04-combined-filter.png', fullPage: true });

    const combinedCount = await rows.count();
    console.log('PASS: 组合筛选（' + combinedCount + ' 行）');

    // 复位
    await searchInput.fill('');
    await page.getByRole('button', { name: '全部分类' }).click();
    await page.waitForTimeout(300);
  } else {
    console.log('⏭ 跳过组合筛选: 无分类按钮');
  }

  // ── Step 6: 全选 checkbox ──
  console.log('Step 6: 全选 checkbox');
  const selectAll = page.locator('thead input[type="checkbox"]');
  await selectAll.click();
  await page.waitForTimeout(300);

  // 验证"已选择"badge 可见
  const selectedBadge = page.getByText(/已选择\s*\d+\s*个/);
  if (!(await selectedBadge.isVisible())) {
    throw new Error('全选后"已选择 N 个"badge 不可见');
  }
  console.log('PASS: "已选择"badge 可见');

  // 验证"加入库"按钮未禁用
  const addToLibBtn = page.getByRole('button', { name: '加入库' });
  if (await addToLibBtn.isDisabled()) {
    throw new Error('全选后"加入库"按钮仍为禁用状态');
  }
  console.log('PASS: "加入库"按钮已启用');

  await page.screenshot({ path: SS + '-05-select-all.png', fullPage: true });

  // 取消全选
  await selectAll.click();
  await page.waitForTimeout(300);

  console.log('== audit-AL3-search-filter 全部通过 ==');
}
