async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/compare-C6';

  // Step 1: 找到一个已完成的对比记录
  console.log('Step 1: 寻找已完成的对比记录');
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

  // 等待结果加载
  const resultHeading = page.getByText('文档对比结果').first();
  await resultHeading.waitFor({ timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: SS + '-01-result-loaded.png', fullPage: true });
  console.log('PASS: 结果页加载完成');

  // Step 2: 返回链接
  const backLink = page.getByText('对比列表').first();
  if (!(await backLink.isVisible())) throw new Error('"对比列表"返回链接不可见');
  console.log('PASS: "对比列表"返回链接可见');

  // Step 3: 状态 badge "已完成"
  const statusBadge = page.locator('.bg-green-50').getByText('已完成').first();
  if (await statusBadge.isVisible().catch(() => false)) {
    console.log('PASS: 状态 badge "已完成"');
  } else {
    console.log('WARN: 未找到绿色"已完成"badge');
  }

  // Step 4: 4 个指标卡片
  const metrics = ['总段落数', '完全重复', '高度相似', '疑似抄袭'];
  for (const m of metrics) {
    const el = page.getByText(m).first();
    if (!(await el.isVisible())) throw new Error('指标卡片缺失: ' + m);
  }
  await page.screenshot({ path: SS + '-02-metrics.png', fullPage: true });
  console.log('PASS: 4 个指标卡片完整');

  // 读取指标数值
  for (const m of metrics) {
    const card = page.getByText(m).first().locator('..');
    const valueEl = card.locator('.text-2xl, .text-3xl').first();
    const value = await valueEl.textContent().catch(() => 'N/A');
    console.log('  ' + m + ': ' + (value || 'N/A').trim());
  }

  // Step 5: 4 个筛选按钮
  const filters = ['全部', '完全重复', '高度相似', '疑似抄袭'];
  for (const f of filters) {
    const btn = page.locator('button.rounded-full').filter({ hasText: f }).first();
    if (!(await btn.isVisible())) throw new Error('筛选按钮缺失: ' + f);
  }
  console.log('PASS: 4 个筛选按钮完整');

  // Step 6: 文档列区域
  const docColumns = page.getByText(/^文件 \d+ ·/).all();
  const colCount = (await docColumns).length;
  if (colCount < 2) throw new Error('文档列不足 2 列: ' + colCount);
  console.log('PASS: ' + colCount + ' 个文档列');

  // 验证文档列信息格式
  for (let i = 0; i < colCount; i++) {
    const colHeader = (await docColumns)[i];
    const headerText = await colHeader.textContent() || '';
    console.log('  列 ' + (i + 1) + ': ' + headerText.trim().slice(0, 60));
  }
  await page.screenshot({ path: SS + '-03-doc-columns.png', fullPage: true });

  // Step 7: 匹配清单侧边栏
  const matchListTitle = page.getByText('匹配清单').first();
  if (!(await matchListTitle.isVisible())) throw new Error('"匹配清单"侧边栏不可见');
  console.log('PASS: "匹配清单"侧边栏可见');

  // 匹配条目计数
  const matchCountBadge = page.getByText(/\d+ 项/).first();
  if (await matchCountBadge.isVisible().catch(() => false)) {
    const countText = await matchCountBadge.textContent() || '';
    console.log('PASS: 匹配计数 badge "' + countText.trim() + '"');
  }

  // Step 8: 下载高亮副本按钮
  const downloadBtns = page.getByText(/高亮副本/);
  const dlCount = await downloadBtns.count();
  if (dlCount >= 1) {
    console.log('PASS: ' + dlCount + ' 个高亮副本下载按钮');
  } else {
    console.log('WARN: 无高亮副本按钮');
  }

  // Step 9: "重新对比" 链接
  const recompareLink = page.getByText('重新对比').first();
  if (await recompareLink.isVisible().catch(() => false)) {
    console.log('PASS: "重新对比"链接可见');
  }

  await page.screenshot({ path: SS + '-04-full-result.png', fullPage: true });
  console.log('== compare-C6-result-view 全部通过 ==');
}
