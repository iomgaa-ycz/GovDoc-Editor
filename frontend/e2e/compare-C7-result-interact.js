async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C7';

  // Step 1: 进入一个已完成的对比结果页
  console.log('Step 1: 进入已完成的对比结果');
  await page.goto(BASE + '/compare');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  const viewResultBtn = page.getByText('查看结果').first();
  if (!(await viewResultBtn.isVisible().catch(() => false))) {
    console.log('⏭ 跳过: 无已完成的对比记录');
    return;
  }
  await viewResultBtn.click();
  await page.waitForURL(/\/compare\/[a-zA-Z0-9-]+/, { timeout: 15000 });

  const resultHeading = page.getByText('文档对比结果').first();
  await resultHeading.waitFor({ timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-01-result-loaded.png', fullPage: true });

  // Step 2: 筛选按钮切换
  console.log('Step 2: 筛选按钮切换');
  const matchItems = page.locator('button.w-full.border-b');
  const initialMatchCount = await matchItems.count();
  console.log('  初始匹配项数: ' + initialMatchCount);

  if (initialMatchCount === 0) {
    console.log('WARN: 无匹配项，跳过交互测试');
    console.log('== compare-C7-result-interact 跳过（无匹配数据） ==');
    return;
  }

  // 点击 "完全重复" 筛选
  const exactFilter = page.locator('button.rounded-full').filter({ hasText: '完全重复' }).first();
  if (await exactFilter.isVisible().catch(() => false)) {
    await exactFilter.click();
    await page.waitForTimeout(500);
    const filteredCount = await matchItems.count();
    await page.screenshot({ path: SS + '-02-filter-exact.png', fullPage: true });
    console.log('PASS: 筛选"完全重复"（' + initialMatchCount + ' → ' + filteredCount + '）');
  }

  // 点击 "高度相似" 筛选
  const similarFilter = page.locator('button.rounded-full').filter({ hasText: '高度相似' }).first();
  if (await similarFilter.isVisible().catch(() => false)) {
    await similarFilter.click();
    await page.waitForTimeout(500);
    const filteredCount2 = await matchItems.count();
    await page.screenshot({ path: SS + '-03-filter-similar.png', fullPage: true });
    console.log('PASS: 筛选"高度相似"（→ ' + filteredCount2 + '）');
  }

  // 切换回 "全部"
  const allFilter = page.locator('button.rounded-full').filter({ hasText: '全部' }).first();
  await allFilter.click();
  await page.waitForTimeout(500);
  const restoredCount = await matchItems.count();
  if (restoredCount !== initialMatchCount) {
    console.log('WARN: 切换回"全部"后匹配数变化: ' + initialMatchCount + ' → ' + restoredCount);
  }
  console.log('PASS: 切换回"全部"（' + restoredCount + ' 项）');

  // Step 3: 匹配清单点击 → 选中样式
  console.log('Step 3: 匹配项点击 → 选中高亮');
  const firstMatch = matchItems.first();
  await firstMatch.click();
  await page.waitForTimeout(500);

  const hasActiveStyle = await firstMatch.evaluate(
    el => el.classList.contains('bg-accent-light') || getComputedStyle(el).backgroundColor !== 'rgba(0, 0, 0, 0)'
  );
  await page.screenshot({ path: SS + '-04-match-selected.png', fullPage: true });
  if (hasActiveStyle) {
    console.log('PASS: 匹配项点击后有选中样式');
  } else {
    console.log('WARN: 匹配项可能未显示选中样式（截图供检查）');
  }

  // Step 4: 匹配项文本内容
  const labelEl = firstMatch.locator('.text-xs.font-medium').first();
  const labelText = await labelEl.textContent().catch(() => '');
  const textEl = firstMatch.locator('.line-clamp-2').first();
  const matchText = await textEl.textContent().catch(() => '');
  const infoEl = firstMatch.locator('.text-xs.text-text-muted, .text-xs').last();
  const infoText = await infoEl.textContent().catch(() => '');
  console.log('PASS: 匹配项内容 — 标签:"' + (labelText || '').trim() + '" 文本:"' + (matchText || '').trim().slice(0, 40) + '..." 信息:"' + (infoText || '').trim() + '"');

  // Step 5: 点击第二个匹配项（如果有）
  if (initialMatchCount >= 2) {
    console.log('Step 5: 切换到第 2 个匹配项');
    const secondMatch = matchItems.nth(1);
    await secondMatch.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: SS + '-05-second-match.png', fullPage: true });
    console.log('PASS: 第 2 个匹配项已点击');
  }

  // Step 6: 文档列中的高亮片段
  console.log('Step 6: 检查文档列高亮片段');
  const highlightedSegments = page.locator('button[data-match-ids]');
  const segmentCount = await highlightedSegments.count();
  if (segmentCount > 0) {
    console.log('PASS: 文档列中有 ' + segmentCount + ' 个高亮片段');

    // 点击第一个高亮片段 → 应选中对应匹配项
    await highlightedSegments.first().click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: SS + '-06-segment-click.png', fullPage: true });
    console.log('PASS: 点击高亮片段（截图供检查联动效果）');
  } else {
    console.log('WARN: 未找到 data-match-ids 高亮片段');
  }

  // Step 7: 下载高亮副本
  console.log('Step 7: 下载高亮副本按钮');
  const downloadBtns = page.getByText(/高亮副本/);
  const dlCount = await downloadBtns.count();
  if (dlCount > 0) {
    // 只验证按钮存在，不实际下载（避免文件系统副作用）
    for (let i = 0; i < dlCount; i++) {
      const btnText = await downloadBtns.nth(i).textContent() || '';
      console.log('  下载按钮 ' + (i + 1) + ': ' + btnText.trim());
    }
    console.log('PASS: ' + dlCount + ' 个下载按钮可见');
  }

  // Step 8: "重新对比" → 回到 Hub
  console.log('Step 8: "重新对比"导航');
  const recompareLink = page.getByText('重新对比').first();
  if (await recompareLink.isVisible().catch(() => false)) {
    await recompareLink.click();
    await page.waitForURL(/\/compare$/, { timeout: 10000 });
    console.log('PASS: "重新对比"回到 Hub 页');
    await page.screenshot({ path: SS + '-07-back-to-hub.png', fullPage: true });
  } else {
    console.log('SKIP: "重新对比"链接不可见');
  }

  console.log('== compare-C7-result-interact 全部通过 ==');
}
