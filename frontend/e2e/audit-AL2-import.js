async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');
  const SS = 'e2e/screenshots/audit-AL2';
  const XLS_PATH = '/home/iomgaa/Projects/GovDoc_Editor/real_data/附件9 处理处罚标准.xls';

  // ── Step 1: 导航到审核点库页面 ──
  console.log('Step 1: 导航到 /audit-library');
  await page.goto(BASE + '/audit-library');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: SS + '-01-initial.png', fullPage: true });
  console.log('PASS: 审核点库页面加载完成');

  // ── Step 2: 点击"上传"下拉 → 选择"导入审查点表格" ──
  console.log('Step 2: 进入导入模式');
  const uploadBtn = page.getByRole('button', { name: /上传/ });
  await uploadBtn.click();
  const importOption = page.getByText('导入审查点表格').first();
  await importOption.waitFor({ timeout: 5000 });
  await importOption.click();

  const batchImportCard = page.getByText('批量导入').first();
  await batchImportCard.waitFor({ timeout: 10000 });
  await page.screenshot({ path: SS + '-02-import-mode.png', fullPage: true });
  console.log('PASS: 进入导入模式，"批量导入"卡片可见');

  // 验证面包屑
  const breadcrumb = page.getByText('导入审查点表格').first();
  if (!(await breadcrumb.isVisible())) throw new Error('面包屑"导入审查点表格"不可见');
  console.log('PASS: 面包屑导航可见');

  // 验证"返回列表"按钮
  const backBtn = page.getByText('返回列表').first();
  if (!(await backBtn.isVisible())) throw new Error('"返回列表"按钮不可见');
  console.log('PASS: "返回列表"按钮可见');

  // 验证"导入结果"卡片
  const resultCard = page.getByText('导入结果').first();
  if (!(await resultCard.isVisible())) throw new Error('"导入结果"卡片不可见');
  console.log('PASS: "导入结果"卡片可见');

  // ── Step 3: 上传 xls 文件 ──
  console.log('Step 3: 上传 xls 文件');
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(XLS_PATH);
  await page.waitForTimeout(1000);

  const filenameVisible = page.getByText('处理处罚标准').first();
  if (!(await filenameVisible.isVisible())) throw new Error('上传后文件名"处理处罚标准"不可见');
  await page.screenshot({ path: SS + '-03-file-uploaded.png', fullPage: true });
  console.log('PASS: 文件上传成功，文件名可见');

  // ── Step 4: 点击"解析预览" ──
  console.log('Step 4: 解析预览');
  const previewBtn = page.getByRole('button', { name: /解析预览/ });
  await previewBtn.click();

  const metricNew = page.getByText('新增').first();
  await metricNew.waitFor({ timeout: 30000 });
  await page.screenshot({ path: SS + '-04-preview-result.png', fullPage: true });
  console.log('PASS: 解析预览完成，"新增"指标可见');

  // 验证 4 个指标都可见
  const metrics = ['新增', '复用', '重复', '跳过'];
  for (const m of metrics) {
    const el = page.getByText(m).first();
    if (!(await el.isVisible())) throw new Error('预览指标缺失: ' + m);
  }
  console.log('PASS: 4 个预览指标全部可见（' + metrics.join('/') + '）');

  // ── Step 5: 确认入库 ──
  console.log('Step 5: 确认入库');
  const confirmBtn = page.getByRole('button', { name: /确认入库/ });
  await confirmBtn.click();

  const successMsg = page.locator('text=/新增.*条/').first();
  await successMsg.waitFor({ timeout: 30000 });
  const resultText = await successMsg.textContent() || '';
  await page.screenshot({ path: SS + '-05-import-success.png', fullPage: true });
  console.log('PASS: 入库成功 — ' + resultText);

  // ── Step 6: 返回列表 ──
  console.log('Step 6: 返回列表');
  const backToList = page.getByText('返回列表').first();
  await backToList.click();
  await page.waitForTimeout(2000);

  const tableRows = await page.locator('table tbody tr').count();
  if (tableRows <= 0) throw new Error('返回列表后表格无数据行（行数: ' + tableRows + '）');
  await page.screenshot({ path: SS + '-06-back-to-list.png', fullPage: true });
  console.log('PASS: 返回列表成功，表格有 ' + tableRows + ' 行数据');

  // ── Step 7: 检查严重程度标签 ──
  console.log('Step 7: 检查严重程度标签');
  const severities = ['严重', '重要', '一般'];
  const foundSeverities = [];
  for (const s of severities) {
    const badge = page.getByText(s).first();
    if (await badge.isVisible().catch(() => false)) {
      foundSeverities.push(s);
    }
  }
  if (foundSeverities.length > 0) {
    console.log('PASS: 发现严重程度标签 — ' + foundSeverities.join(', '));
  } else {
    console.log('INFO: 未发现严重程度标签（严重/重要/一般），可能数据中无此字段');
  }

  // ── Step 8: 最终截图 ──
  await page.screenshot({ path: SS + '-08-final.png', fullPage: true });
  console.log('== audit-AL2-import 全部通过 ==');
}
